#!/usr/bin/env python3
"""Release one image: mirror upstream -> candidate -> GPU smoke in a CI slot -> rc-current -> catalog (GT, Global, China).

  release.py <image> [--sites gt,global,china] [--dry-run]

Inputs: images/<image>/{Dockerfile,image.yaml,smoke.sh}. Harbor creds via $DOCKER_CONFIG, catalog tokens via
$CATALOG_TOKEN_DIR (both k8s Secret mounts on the runner). Nothing secret is printed.
A FROM-only Dockerfile is released as the mirrored upstream image itself (same digest); Dockerfiles with build
steps are built with Kaniko in the slot namespace (not in the first batch).
"""
import argparse, json, os, re, subprocess, sys, time, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import harbor  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PULL = "10.5.10.12:1808/radeon-cloud-global"
PUSH = "36.150.116.202:1808/radeon-cloud-global"


def sh(*cmd, check=True, **kw):
    r = subprocess.run(cmd, text=True, capture_output=True, **kw)
    if check and r.returncode:
        raise SystemExit(f"{cmd[0]} failed ({r.returncode}): {r.stderr[-800:]}")
    return r.stdout


def parse(image):
    d = os.path.join(ROOT, "images", image)
    df = open(os.path.join(d, "Dockerfile")).read()
    up = re.search(r"^# upstream: ([^/\s]+)/(\S+?):([^:@/\s]+)@(sha256:[0-9a-f]{64})", df, re.M)
    frm = re.search(r"^FROM\s+(\S+)", df, re.M)
    if not up or not frm:
        raise SystemExit("Dockerfile needs a '# upstream: <registry>/<repo>:<tag>@sha256:...' line and a FROM")
    build_steps = [l for l in df.splitlines() if l.strip() and not l.lstrip().startswith("#") and not l.startswith("FROM")]
    cfg = {}
    for l in open(os.path.join(d, "image.yaml")):
        m = re.match(r"^(\w+):\s*(.*?)\s*(?:#.*)?$", l)
        if m and m.group(2):
            cfg[m.group(1)] = m.group(2).strip("'\"")
    mirror_repo = frm.group(1).split("@")[0].replace(PULL + "/", "")
    return {"dir": d, "registry": up.group(1), "repo": up.group(2), "tag": up.group(3), "digest": up.group(4),
            "from": frm.group(1), "mirror_repo": mirror_repo, "build": bool(build_steps), **cfg}


def ensure_mirror(m):
    if harbor.artifact(m["mirror_repo"], m["digest"]):
        print(f"mirror: {m['mirror_repo']}@{m['digest'][:19]} already in Harbor")
        return
    out = tempfile.mkdtemp(prefix="mirror-")
    target = f"{PUSH}/{m['mirror_repo']}:{m['tag']}"
    print(f"mirror: fetching {m['repo']}@{m['digest'][:19]} -> {target}")
    r = subprocess.run([os.path.join(ROOT, "tools", "mirror.sh"), m["repo"], m["digest"], out, target], text=True)
    if r.returncode or not harbor.artifact(m["mirror_repo"], m["digest"]):
        raise SystemExit("mirror failed or digest not in Harbor afterwards")


SLOT_POOL = [sys.executable, os.path.join(ROOT, "tools", "ci", "slot_pool.py")]


def slot_acquire():
    """Claim one CI slot (same lease protocol as RCI CI). Leaves it 'allocated'; we never deploy a stack into it."""
    r = subprocess.run(SLOT_POOL + ["acquire", "--wait-seconds", "3600"], text=True, capture_output=True)
    last = (r.stdout.strip().splitlines() or ["{}"])[-1]
    slot = json.loads(last) if last.startswith("{") else {}
    if r.returncode or slot.get("acquired") != "true":
        raise SystemExit(f"could not claim a CI slot: {r.stdout[-300:]} {r.stderr[-300:]}")
    print(f"slot: {slot['id']} ({slot['namespace']})")
    return slot["namespace"]


def slot_release(job_gone):
    """Release only when our Job is confirmed gone; otherwise quarantine so RCI CI never gets a busy GPU slot."""
    cmd = "release" if job_gone else "quarantined"
    r = subprocess.run(SLOT_POOL + [cmd], text=True, capture_output=True)
    print(f"slot: {cmd} rc={r.returncode} {r.stdout.strip()[-200:]}")


def smoke(m, candidate):
    ns = slot_acquire()
    try:
        _smoke_in(ns, m, candidate)
    finally:
        gone = subprocess.run(["kubectl", "-n", ns, "get", "jobs", "-l", "app.kubernetes.io/part-of=radeon-cloud-images",
                               "-o", "name"], text=True, capture_output=True).stdout.strip() == ""
        slot_release(gone)


def _smoke_in(ns, m, candidate):
    name = f"rcimg-smoke-{m['name']}-{int(time.time())}"[:62]
    cm = sh("kubectl", "-n", ns, "create", "configmap", name, f"--from-file=smoke.sh={m['dir']}/smoke.sh", "-o", "name")
    job = {"apiVersion": "batch/v1", "kind": "Job",
           "metadata": {"name": name, "namespace": ns, "labels": {"app.kubernetes.io/part-of": "radeon-cloud-images"}},
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 1800, "ttlSecondsAfterFinished": 3600, "template": {"spec": {
               "restartPolicy": "Never",
               "nodeSelector": {"amd-oneclick.io/workload-ci": "enabled"},
               "containers": [{"name": "smoke", "image": candidate, "command": ["/bin/bash", "/smoke/smoke.sh"],
                               "env": [{"name": "SMOKE_MODEL_DIR", "value": "/models/Qwen2.5-0.5B-Instruct"}],
                               "resources": {"limits": {"amd.com/gpu": "1", "memory": "48Gi", "cpu": "8"},
                                             "requests": {"amd.com/gpu": "1", "memory": "16Gi", "cpu": "4"}},
                               "volumeMounts": [{"name": "smoke", "mountPath": "/smoke"}]}],
               "volumes": [{"name": "smoke", "configMap": {"name": name}}]}}}}
    subprocess.run(["kubectl", "apply", "-f", "-"], input=json.dumps(job), text=True, check=True, capture_output=True)
    try:
        r = subprocess.run(["kubectl", "-n", ns, "wait", f"job/{name}", "--for=condition=complete", "--timeout=1800s"],
                           text=True, capture_output=True)
        logs = sh("kubectl", "-n", ns, "logs", f"job/{name}", "--tail=200", check=False)
        print(logs)
        ok = r.returncode == 0 and "SMOKE PASS" in logs
    finally:
        sh("kubectl", "-n", ns, "delete", "job", name, "--wait=true", "--timeout=180s", check=False)
        sh("kubectl", "-n", ns, "delete", cm, check=False)
    if not ok:
        raise SystemExit(f"smoke failed for {candidate}")


def promote(m, digest):
    rc = m["rc_repo"]
    harbor.copy(rc, m["mirror_repo"], digest)
    cur = harbor.artifact(rc, "rc-current")
    if cur and cur["digest"] != digest:
        harbor.tag(rc, cur["digest"], "rc-prev")
    harbor.tag(rc, digest, "rc-current")
    print(f"harbor: {rc}:rc-current -> {digest}" + (f" (rc-prev {cur['digest'][:19]})" if cur and cur['digest'] != digest else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--sites", default="gt,global,china")
    ap.add_argument("--skip-smoke", action="store_true", help="only for rollback to an already-smoked digest")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smoke-only", action="store_true", help="PR check: mirror + smoke, no rc-current move, no catalog")
    a = ap.parse_args()
    m = parse(a.image)
    print(json.dumps({k: v for k, v in m.items() if k != "dir"}, ensure_ascii=False))
    if m["build"]:
        raise SystemExit("Dockerfiles with build steps are not supported in the first batch")
    if a.dry_run:
        return
    ensure_mirror(m)
    candidate = f"{PULL}/{m['mirror_repo']}@{m['digest']}"
    if not a.skip_smoke:
        smoke(m, candidate)
    if a.smoke_only:
        print(f"SMOKE OK {a.image} {m['digest']} (not promoted)")
        return
    promote(m, m["digest"])
    import catalog
    for site in [s for s in a.sites.split(",") if s]:
        print(f"[{site}] {m['catalog_row']}: {catalog.adopt(site, m['catalog_row'], m['digest'])}")
    print(f"RELEASED {a.image} {m['digest']}")


if __name__ == "__main__":
    main()
