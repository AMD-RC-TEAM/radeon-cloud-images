#!/usr/bin/env python3
"""Release one image: mirror upstream -> candidate -> GPU smoke on the CI node -> move rc-current (D-20261112-33).

  release.py <image> [--smoke-only] [--dry-run]

Inputs: images/<image>/{Dockerfile,image.yaml,smoke.sh}. Harbor creds via $DOCKER_CONFIG (k8s Secret on the runner).
Nothing secret is printed. CI stops at rc-current: the catalog rows that track rc-current are updated outside CI.
A FROM-only Dockerfile is released as the mirrored upstream image itself (same digest). A Dockerfile with build
steps is built with Kaniko in the runner namespace (no GPU) into build/<image>:ctx-<hash of the build context>; a
context that was already built (for example by the PR check) is reused, so the release ships the digest that passed
the smoke.
"""
import argparse, hashlib, io, json, os, re, signal, subprocess, sys, tarfile, time, tempfile, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
import harbor  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PULL = "10.5.10.12:1808/radeon-cloud-global"
PUSH = "36.150.116.202:1808/radeon-cloud-global"
BUILD_NS = "amd-oneclick-ci-runners"
KANIKO = PULL + "/kaniko-project/executor@sha256:8a4f9af8ef55ef8bfaf4cfd7b15dc956609e14a4402efefd5fb2e49a0c06e2c8"  # v1.23.2
PIP_INDEX = "https://mirrors.aliyun.com/pypi/simple/"   # pypi.org is not reachable from the cluster
HF_ENDPOINT = "https://hf-mirror.com"                   # huggingface.co is not reachable either
HF_CACHE_HOSTPATH = "/nvme0/data/rc-images-ci-hf-cache"   # on the CI node (amd-oneclick.io/workload-ci=enabled)


def sh(*cmd, check=True, **kw):
    r = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if check and r.returncode:
        raise SystemExit(f"{cmd[0]} failed ({r.returncode}): {r.stderr[-800:]}")
    return r.stdout


FROM_RE = re.compile(r"^FROM\s+(?P<ref>(?P<registry>[^/\s]+)/(?P<repo>\S+?):(?P<tag>[^:@/\s]+)@(?P<digest>sha256:[0-9a-f]{64}))\s*$", re.M)


# Every image gets the same last build step: keep the image's toolchain environment in SSH sessions (the platform's
# sshd starts sessions with a minimal environment; see tools/keep_image_env.sh). It is added here, from one shared
# copy, so no image directory carries the script and a new image cannot miss it; the smoke checks it for every image.
KEEP_ENV_SCRIPT = os.path.join(ROOT, "tools", "keep_image_env.sh")
KEEP_ENV_NAME = "rc-keep-image-env.sh"   # its name in the build context
KEEP_ENV_STEP = os.path.join(ROOT, "tools", "keep_image_env.step")   # the Dockerfile lines added (template)


def with_keep_env_step(df):
    """The Dockerfile plus the shared SSH-environment step, as the final step (after every ENV). If the final stage
    switches USER, the step runs as root and that USER is restored. Build ARG names (not also set by ENV) are passed
    to the script so build arguments never reach SSH sessions."""
    last = df[max((m.start() for m in re.finditer(r"^FROM\s", df, re.M)), default=0):]   # the final stage only
    users = re.findall(r"^USER\s+(\S+)", last, re.M)
    args = set(re.findall(r"^ARG\s+([A-Za-z_][A-Za-z0-9_]*)", df, re.M))
    envs = set(re.findall(r"^ENV\s+([A-Za-z_][A-Za-z0-9_]*)", df, re.M))
    skip = " ".join(sorted(args - envs))   # build arguments are not the image's environment
    text = open(KEEP_ENV_STEP).read().format(skip=f'RC_KEEP_ENV_SKIP="{skip}" ' if skip else "").rstrip("\n")
    step = [""] + (["USER root"] if users else []) + text.splitlines() + ([f"USER {users[-1]}"] if users else [])
    return df.rstrip("\n") + "\n" + "\n".join(step) + "\n"


def parse(image):
    """images/<image>/Dockerfile must FROM the real public upstream, pinned: FROM <registry>/<repo>:<tag>@sha256:<digest>.
    The tooling mirrors that digest into Harbor on demand and builds/smokes from the Harbor copy, so cluster nodes
    never pull from the internet. Hand-written Harbor paths are refused."""
    d = os.path.join(ROOT, "images", image)
    df = open(os.path.join(d, "Dockerfile")).read()
    frm = FROM_RE.search(df)
    if not frm:
        raise SystemExit(f"{image}: the Dockerfile needs 'FROM <registry>/<repo>:<tag>@sha256:<digest>' "
                         "(the public upstream, e.g. docker.io/rocm/pytorch:<tag>@sha256:...)")
    if frm["registry"].startswith(("10.5.10.12", "36.150.116.202")) or len(FROM_RE.findall(df)) > 1:
        raise SystemExit(f"{image}: FROM must name the public upstream once, not our Harbor (the tooling mirrors it)")
    cfg = {}
    for l in open(os.path.join(d, "image.yaml")):
        m = re.match(r"^(\w+):\s*(.*?)\s*(?:#.*)?$", l)
        if m and m.group(2):
            cfg[m.group(1)] = m.group(2).strip("'\"")
    reg = frm["registry"]
    mirror_repo = frm["repo"] if reg == "docker.io" else f"{reg}/{frm['repo']}"
    harbor_ref = f"{PULL}/{mirror_repo}@{frm['digest']}"
    return {"dir": d, "registry": reg, "repo": frm["repo"], "tag": frm["tag"], "digest": frm["digest"],
            "from": frm["ref"], "mirror_repo": mirror_repo, "harbor_ref": harbor_ref,
            "build_dockerfile": with_keep_env_step(df.replace(frm["ref"], harbor_ref, 1)), "build": True, **cfg}


def ensure_mirror(m):
    if harbor.artifact(m["mirror_repo"], m["digest"]):
        print(f"mirror: {m['mirror_repo']}@{m['digest'][:19]} already in Harbor")
        return
    if m["registry"] != "docker.io":
        raise SystemExit(f"{m['registry']}/{m['repo']}@{m['digest'][:19]} is not in Harbor and only Docker Hub upstreams are "
                         f"mirrored automatically; copy it into radeon-cloud-global/{m['mirror_repo']} first (rc-ops)")
    out = tempfile.mkdtemp(prefix="mirror-")
    target = f"{PUSH}/{m['mirror_repo']}:{m['tag']}"
    print(f"mirror: fetching {m['repo']}@{m['digest'][:19]} -> {target}")
    r = subprocess.run([os.path.join(ROOT, "tools", "mirror.sh"), m["repo"], m["digest"], out, target], text=True)
    if r.returncode or not harbor.artifact(m["mirror_repo"], m["digest"]):
        raise SystemExit("mirror failed or digest not in Harbor afterwards")


def context_files(m):
    """Everything in the image directory except the release settings and the smoke script, plus the shared
    SSH-environment script (with_keep_env_step).
    Returns sorted (name in the context, local path)."""
    files = [(f, os.path.join(m["dir"], f)) for f in os.listdir(m["dir"])
             if f not in ("image.yaml", "smoke.sh") and os.path.isfile(os.path.join(m["dir"], f))]
    return sorted(files + [(KEEP_ENV_NAME, KEEP_ENV_SCRIPT)])


def context_tag(m):
    h = hashlib.sha256()
    for f, path in context_files(m):
        if f == "Dockerfile":   # what is built: FROM rewritten to Harbor; comments and blank lines do not matter
            data = "\n".join(l for l in m["build_dockerfile"].splitlines()
                             if l.strip() and not l.lstrip().startswith("#")).encode()
        else:
            data = open(path, "rb").read()
        h.update(f.encode() + b"\0" + data + b"\0")
    return "ctx-" + h.hexdigest()[:20]


# Kaniko build time limit. Builds have no layer cache and snapshot the whole filesystem after each RUN, so a big
# image's from-scratch build is slow: comfyui (ROCm 7.14 base, ~20 GB) took ~85 min on 11-24, and one more RUN step
# pushed it past the old 90-min limit (images#43, 11-25). At 120 min it built in ~116, too close to rely on, so 180.
# Lower it again once builds get a layer cache (planned).
BUILD_DEADLINE_S = 10800


# Every Job we create carries the GitHub run that owns it, so a later run can clean up after a cancelled one.
RUN_ID = f"{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '0')}"
SMOKE_MAX = int(os.environ.get("RC_SMOKE_MAX_CONCURRENT", "2"))  # GPUs image smokes may hold on the CI node at once


def job_labels(kind):
    return {"app.kubernetes.io/part-of": "radeon-cloud-images", "radeon-cloud-images/kind": kind,
            "radeon-cloud-images/run": RUN_ID}


def reap_stale_jobs():
    """Delete our Jobs (and their ConfigMaps) whose GitHub run is no longer in progress: a cancelled run cannot clean up
    after itself if it was killed before its finally blocks. Asks GitHub only; if that fails, reaps nothing."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        return
    out = sh("kubectl", "-n", BUILD_NS, "get", "jobs", "-l", "radeon-cloud-images/run", "-o", "json", check=False)
    jobs = json.loads(out).get("items", []) if out.strip() else []
    status = {}
    for j in jobs:
        run = j["metadata"]["labels"].get("radeon-cloud-images/run", "")
        if run == RUN_ID or not run.split("-")[0].isdigit():
            continue
        if run not in status:
            try:
                req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/runs/{run.split('-')[0]}",
                                             headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
                status[run] = json.loads(urllib.request.urlopen(req, timeout=20).read()).get("status")
            except Exception as e:      # noqa: BLE001 (no answer = leave it alone)
                print(f"reaper: could not ask GitHub about run {run}: {e}"); status[run] = None
        if status[run] == "completed":
            name = j["metadata"]["name"]
            print(f"reaper: deleting {name} (its run {run} has finished)")
            sh("kubectl", "-n", BUILD_NS, "delete", "job", name, "--wait=false", check=False)
            sh("kubectl", "-n", BUILD_NS, "delete", "configmap", name, "--ignore-not-found", check=False)


def wait_for_smoke_capacity(limit_s=7200):
    """At most SMOKE_MAX image smokes hold CI-node GPUs at once; the rest wait here (the node is shared with RCI CI).
    Two runs can pass this check at the same moment, so the cap can be exceeded by one for a short while."""
    deadline = time.time() + limit_s
    while True:
        out = sh("kubectl", "-n", BUILD_NS, "get", "jobs", "-l", "radeon-cloud-images/kind=smoke", "-o", "json", check=False)
        active = [j for j in (json.loads(out).get("items", []) if out.strip() else [])
                  if not any(c.get("status") == "True" and c.get("type") in ("Complete", "Failed")
                             for c in j.get("status", {}).get("conditions", []))]
        if len(active) < SMOKE_MAX:
            return
        if time.time() > deadline:
            raise SystemExit(f"smoke: {len(active)} image smokes still running after {limit_s} s (cap {SMOKE_MAX})")
        print(f"smoke: waiting, {len(active)} image smokes already running (cap {SMOKE_MAX})"); time.sleep(30)


def build(m):
    """Build the image with Kaniko, or reuse an earlier build of the same context. Returns (repo, digest)."""
    repo, tag = f"build/{m['name']}", context_tag(m)
    done = harbor.artifact(repo, tag)
    if done:
        print(f"build: {repo}:{tag} already built ({done['digest'][:19]}), reusing it")
        return repo, done["digest"]
    name = f"rcimg-build-{m['name']}-{int(time.time())}"[:62]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for f, path in context_files(m):
            if f == "Dockerfile":
                data = m["build_dockerfile"].encode()
                ti = tarfile.TarInfo("Dockerfile"); ti.size = len(data); ti.mode = 0o644
                t.addfile(ti, io.BytesIO(data))
            else:
                t.add(path, arcname=f)
    tmp = tempfile.mkdtemp(prefix="ctx-")
    with open(os.path.join(tmp, "context.tar.gz"), "wb") as f:
        f.write(buf.getvalue())
    cm = sh("kubectl", "-n", BUILD_NS, "create", "configmap", name, f"--from-file=context.tar.gz={tmp}/context.tar.gz",
            "-o", "name").strip()
    labels = job_labels("build")
    job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": name, "namespace": BUILD_NS, "labels": labels},
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": BUILD_DEADLINE_S, "ttlSecondsAfterFinished": 3600, "template": {
               "metadata": {"labels": labels},
               "spec": {"restartPolicy": "Never", "automountServiceAccountToken": False,
                        "containers": [{"name": "kaniko", "image": KANIKO, "args": [
                            "--context=tar:///context/context.tar.gz", "--dockerfile=Dockerfile",
                            f"--destination={PUSH}/{repo}:{tag}", "--digest-file=/dev/termination-log",
                            f"--build-arg=PIP_INDEX_URL={PIP_INDEX}",
                            "--insecure", "--insecure-pull", "--skip-tls-verify", "--skip-tls-verify-pull",
                            "--snapshot-mode=redo", "--use-new-run", "--compressed-caching=false",
                            "--push-retry=3", "--image-fs-extract-retry=3"],
                            "resources": {"requests": {"cpu": "4", "memory": "16Gi", "ephemeral-storage": "150Gi"},
                                          "limits": {"cpu": "16", "memory": "48Gi", "ephemeral-storage": "300Gi"}},
                            "volumeMounts": [{"name": "context", "mountPath": "/context"},
                                             {"name": "docker", "mountPath": "/kaniko/.docker", "readOnly": True}]}],
                        "volumes": [{"name": "context", "configMap": {"name": name}},
                                    {"name": "docker", "secret": {"secretName": "radeon-images-harbor", "items": [
                                        {"key": ".dockerconfigjson", "path": "config.json"}]}}]}}}}
    subprocess.run(["kubectl", "apply", "-f", "-"], input=json.dumps(job), text=True, check=True, capture_output=True)
    print(f"build: Kaniko job {BUILD_NS}/{name} -> {repo}:{tag}")
    try:
        # Stop polling 120 s before the Job's own deadline (as smoke() does): at the deadline Kubernetes deletes the
        # pod, and with it the build log printed below (11-26: images#50's timed-out build left no log).
        ok, deadline = False, time.time() + BUILD_DEADLINE_S - 120
        while time.time() < deadline:
            st = json.loads(sh("kubectl", "-n", BUILD_NS, "get", "job", name, "-o", "json")).get("status", {})
            if st.get("succeeded"):
                ok = True; break
            if st.get("failed"):
                break
            time.sleep(30)
        print(sh("kubectl", "-n", BUILD_NS, "logs", f"job/{name}", "--tail=60", check=False))
        if not ok:
            print(sh("kubectl", "-n", BUILD_NS, "get", "pods", "-l", f"job-name={name}", "-o", "wide", check=False))
            if time.time() >= deadline:
                raise SystemExit(f"build for {m['name']} did not finish within {BUILD_DEADLINE_S // 60} min (log above)")
            raise SystemExit(f"build failed for {m['name']}")
    finally:
        sh("kubectl", "-n", BUILD_NS, "delete", "job", name, "--wait=false", check=False)
        sh("kubectl", "-n", BUILD_NS, "delete", cm, check=False)
    built = harbor.artifact(repo, tag)
    if not built:
        raise SystemExit(f"build reported success but {repo}:{tag} is not in Harbor")
    print(f"build: {repo}:{tag} = {built['digest']}")
    return repo, built["digest"]


def smoke(m, candidate):
    """One GPU on the CI node, as a Job in the runner namespace.

    The smoke deploys no stack, so it takes none of the RCI CI slots: a slot is a whole test stack that RCI's PR
    checks queue for, and holding one for a single-GPU Job stopped them (11-26: one failed smoke held a slot for
    58 minutes). The scheduler hands out the node's GPUs; a smoke that cannot get one
    stays Pending and fails at its deadline with the reason printed.
    """
    wait_for_smoke_capacity()
    _smoke_in(BUILD_NS, m, candidate)


def _smoke_in(ns, m, candidate):
    name = f"rcimg-smoke-{m['name']}-{int(time.time())}"[:62]
    cm = sh("kubectl", "-n", ns, "create", "configmap", name, f"--from-file=smoke.sh={m['dir']}/smoke.sh",
            f"--from-file=smoke_lib.sh={ROOT}/tools/smoke_lib.sh",
            f"--from-file=hk_readme_smoke.sh={ROOT}/tools/hk_readme_smoke.sh",
            f"--from-file=versions_probe.py={ROOT}/tools/versions_probe.py", "-o", "name")
    job = {"apiVersion": "batch/v1", "kind": "Job",
           "metadata": {"name": name, "namespace": ns, "labels": job_labels("smoke")},
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 3600, "ttlSecondsAfterFinished": 3600, "template": {
               "metadata": {"labels": job_labels("smoke")}, "spec": {
               "restartPolicy": "Never", "automountServiceAccountToken": False,
               "nodeSelector": {"amd-oneclick.io/workload-ci": "enabled"},
               "containers": [{"name": "smoke", "image": candidate, "command": ["/bin/bash", "-c", VERSIONS_AFTER_SMOKE],
                               "env": [{"name": "SMOKE_MODEL_DIR", "value": "/models/Qwen2.5-0.5B-Instruct"},
                                       {"name": "HF_ENDPOINT", "value": HF_ENDPOINT},
                                       # Persistent HF cache on the CI node (seeded with Qwen3-8B and the SD1.5 fp16
                                       # checkpoint) so a release does not re-download ~18 GB per image.
                                       {"name": "HF_HOME", "value": "/hf-cache"}],
                               "resources": {"limits": {"amd.com/gpu": "1", "memory": "48Gi", "cpu": "8"},
                                             "requests": {"amd.com/gpu": "1", "memory": "16Gi", "cpu": "4"}},
                               "volumeMounts": [{"name": "smoke", "mountPath": "/smoke"},
                                                {"name": "hf-cache", "mountPath": "/hf-cache"}]}],
               "volumes": [{"name": "smoke", "configMap": {"name": name}},
                           {"name": "hf-cache", "hostPath": {"path": HF_CACHE_HOSTPATH, "type": "DirectoryOrCreate"}}]}}}}
    subprocess.run(["kubectl", "apply", "-f", "-"], input=json.dumps(job), text=True, check=True, capture_output=True)
    try:
        # Give up before the Job's activeDeadlineSeconds (3600): at the deadline Kubernetes deletes the pod and its
        # logs, so a hung smoke used to fail with no output at all (11-13 #15).
        # Polled, as build() does: `kubectl wait --for=condition=complete` never returns for a Job that failed, so a
        # smoke that died in 8 seconds was waited on for the whole 58 minutes (11-26).
        passed, deadline = False, time.time() + 3480
        while time.time() < deadline:
            st = json.loads(sh("kubectl", "-n", ns, "get", "job", name, "-o", "json")).get("status", {})
            if st.get("succeeded"):
                passed = True; break
            if st.get("failed"):
                break
            time.sleep(10)
        logs = sh("kubectl", "-n", ns, "logs", f"job/{name}", "--tail=200", check=False)
        print(logs)
        ok = passed and "SMOKE PASS" in logs
        if ok:
            report_versions(m["name"], candidate, logs)
        if not ok:
            # Say why before the Job is deleted (11-12: a smoke sat 30 min with no output).
            print("smoke did not pass; pod state:")
            print(sh("kubectl", "-n", ns, "get", "pods", "-l", f"job-name={name}", "-o",
                     "custom-columns=POD:.metadata.name,PHASE:.status.phase,NODE:.spec.nodeName,"
                     "WAITING:.status.containerStatuses[0].state.waiting.reason,"
                     "TERMINATED:.status.containerStatuses[0].state.terminated.reason,"
                     "SCHEDULED:.status.conditions[?(@.type=='PodScheduled')].message", check=False))
            print(sh("kubectl", "-n", ns, "describe", "pods", "-l", f"job-name={name}", check=False)[-2500:])
    finally:
        sh("kubectl", "-n", ns, "delete", "job", name, "--wait=false", check=False)
        sh("kubectl", "-n", ns, "delete", cm, check=False)
    if not ok:
        raise SystemExit(f"smoke failed for {candidate}")


# The smoke ends with the versions probe; its RC-VERSIONS line is the source of the picker description (D-20261114-08).
# Every image: the shared SSH-environment check first (the step with_keep_env_step adds), then the image's own smoke.
VERSIONS_AFTER_SMOKE = ("/bin/bash -c '. /smoke/smoke_lib.sh && ssh_keeps_image_env' && /bin/bash /smoke/smoke.sh"
                        " && { python3 /smoke/versions_probe.py || echo 'RC-VERSIONS {}'; }")
VERSIONS_RE = re.compile(r"^RC-VERSIONS (\{.*\})\s*$", re.M)


def report_versions(name, ref, logs):
    """Print one 'RC-VERSIONS-OF <digest> <json>' line (catalog_sync reads it from this run's log) and keep a copy."""
    found = VERSIONS_RE.findall(logs)
    if not found:
        print(f"versions: no RC-VERSIONS line for {name}")
        return None
    v = json.loads(found[-1])
    digest = ref.rsplit("@", 1)[-1]
    print(f"RC-VERSIONS-OF {digest} " + json.dumps({"image": name, "versions": v}, separators=(",", ":")))
    out = os.environ.get("RC_VERSIONS_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, f"versions-{name}-{digest[7:19]}.json"), "w") as f:
            json.dump({"image": name, "ref": ref, "digest": digest, "versions": v}, f, indent=1)
    return v


def probe(ref, name="probe"):
    """Run only the versions probe in an existing image (no GPU): for backfilling rows released earlier."""
    if "@sha256:" not in ref:
        raise SystemExit("probe needs an image reference pinned by digest")
    job_name = f"rcimg-versions-{name}-{int(time.time())}"[:62]
    labels = job_labels("probe")
    cm = sh("kubectl", "-n", BUILD_NS, "create", "configmap", job_name,
            f"--from-file=versions_probe.py={ROOT}/tools/versions_probe.py", "-o", "name").strip()
    job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": job_name, "namespace": BUILD_NS, "labels": labels},
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 2400, "ttlSecondsAfterFinished": 3600, "template": {
               "metadata": {"labels": labels},
               "spec": {"restartPolicy": "Never", "automountServiceAccountToken": False,
                        # The CI node already holds the released images, so most probes start without a pull.
                        "nodeSelector": {"amd-oneclick.io/workload-ci": "enabled"},
                        "containers": [{"name": "probe", "image": ref,
                                        # The runner's ServiceAccount cannot read pod logs in this namespace, so the line also
                                        # goes to the termination message (read from the pod status, as build() does).
                                        "command": ["/bin/sh", "-c", "{ python3 /probe/versions_probe.py || python /probe/versions_probe.py; } | tee /dev/termination-log"],
                                        "resources": {"requests": {"cpu": "100m", "memory": "256Mi"},
                                                      "limits": {"cpu": "1", "memory": "2Gi"}},
                                        "volumeMounts": [{"name": "probe", "mountPath": "/probe"}]}],
                        "volumes": [{"name": "probe", "configMap": {"name": job_name}}]}}}}
    subprocess.run(["kubectl", "apply", "-f", "-"], input=json.dumps(job), text=True, check=True, capture_output=True)
    try:
        # Poll like build() does: the runner's ServiceAccount can get Jobs but `kubectl wait` (watch) failed in CI.
        ok, deadline = False, time.time() + 2300
        while time.time() < deadline:
            st = json.loads(sh("kubectl", "-n", BUILD_NS, "get", "job", job_name, "-o", "json")).get("status", {})
            if st.get("succeeded"):
                ok = True; break
            if st.get("failed"):
                break
            time.sleep(10)
        logs = sh("kubectl", "-n", BUILD_NS, "logs", f"job/{job_name}", "--tail=20", check=False)
        logs += "\n" + sh("kubectl", "-n", BUILD_NS, "get", "pods", "-l", f"job-name={job_name}", "-o",
                          "jsonpath={..state.terminated.message}", check=False)
        print(logs)
        if not ok:
            print(sh("kubectl", "-n", BUILD_NS, "get", "pods", "-l", f"job-name={job_name}", "-o", "wide", check=False))
    finally:
        sh("kubectl", "-n", BUILD_NS, "delete", "job", job_name, "--wait=false", check=False)
        sh("kubectl", "-n", BUILD_NS, "delete", cm, check=False)
    if not ok or not report_versions(name, ref, logs):
        raise SystemExit(f"versions probe failed for {ref}")


def promote(m, src_repo, digest):
    rc = m["rc_repo"]
    harbor.copy(rc, src_repo, digest)
    cur = harbor.artifact(rc, "rc-current")
    if cur and cur["digest"] != digest:
        harbor.tag(rc, cur["digest"], "rc-prev")
    harbor.tag(rc, digest, "rc-current")
    print(f"harbor: {rc}:rc-current -> {digest}" + (f" (rc-prev {cur['digest'][:19]})" if cur and cur['digest'] != digest else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="image dir under images/, or with --probe a <name>=<ref@sha256:...> pair")
    ap.add_argument("--skip-smoke", action="store_true", help="only for rollback to an already-smoked digest")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smoke-only", action="store_true", help="PR check: mirror + smoke, no rc-current move, no catalog")
    ap.add_argument("--probe", action="store_true", help="only print the versions of an existing digest (no GPU)")
    a = ap.parse_args()
    # GitHub cancels a run with SIGTERM. Exit normally on it, so the finally blocks delete this run's Jobs.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    if not a.dry_run:
        reap_stale_jobs()
    if a.probe:
        failed = []
        for item in a.image.split():
            name, _, ref = item.partition("=")
            try:
                probe(ref, name)
            except SystemExit as e:   # keep going: one bad digest must not hide the others
                print(e); failed.append(name)
        if failed:
            raise SystemExit(f"versions probe failed for: {', '.join(failed)}")
        return
    m = parse(a.image)
    print(json.dumps({k: v for k, v in m.items() if k != "dir"}, ensure_ascii=False))
    if a.dry_run:
        if m["build"]:
            print(f"build context {context_tag(m)}: {', '.join(f for f, _ in context_files(m))}")
        return
    ensure_mirror(m)   # the upstream image, or the base image of a build
    src_repo, digest = build(m) if m["build"] else (m["mirror_repo"], m["digest"])
    candidate = f"{PULL}/{src_repo}@{digest}"
    if not a.skip_smoke:
        smoke(m, candidate)
    if a.smoke_only:
        print(f"SMOKE OK {a.image} {digest} (not promoted)")
        return
    promote(m, src_repo, digest)
    print(f"RELEASED {a.image} {m['rc_repo']}:rc-current = {digest}")


if __name__ == "__main__":
    main()
