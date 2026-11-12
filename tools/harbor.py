"""Minimal Harbor v2 API client (pull/API host is internal; credentials come from a docker config file)."""
import base64, json, os, urllib.error, urllib.parse, urllib.request

API = os.environ.get("HARBOR_API", "http://10.5.10.12:1808")
PROJECT = os.environ.get("HARBOR_PROJECT", "radeon-cloud-global")


def _auth():
    cfg = json.load(open(os.path.join(os.environ.get("DOCKER_CONFIG", os.path.expanduser("~/.docker")), "config.json")))
    for host, v in cfg.get("auths", {}).items():
        if host.split("://")[-1].startswith(("10.5.10.12", "36.150.116.202")):
            return v.get("auth") or base64.b64encode(f"{v['username']}:{v['password']}".encode()).decode()
    raise SystemExit("no Harbor credentials in docker config")


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Basic " + _auth(), "Accept": "application/json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]


def _repo(name):
    return f"/api/v2.0/projects/{PROJECT}/repositories/" + urllib.parse.quote(urllib.parse.quote(name, safe=""), safe="")


def artifact(repo, ref):
    st, body = call("GET", _repo(repo) + "/artifacts/" + urllib.parse.quote(ref, safe=":"))
    return body if st == 200 else None


def copy(dst_repo, src_repo, digest):
    st, body = call("POST", _repo(dst_repo) + "/artifacts?from=" + urllib.parse.quote(f"{PROJECT}/{src_repo}@{digest}", safe=""))
    if st not in (200, 201, 409):
        raise SystemExit(f"harbor copy {src_repo}@{digest} -> {dst_repo}: {st} {body}")


def tag(repo, digest, name):
    """Point tag `name` at `digest` (deletes it from its old artifact first)."""
    old = artifact(repo, name)
    if old and old.get("digest") == digest:
        return
    if old:
        call("DELETE", _repo(repo) + f"/artifacts/{old['digest']}/tags/{urllib.parse.quote(name)}")
    st, body = call("POST", _repo(repo) + f"/artifacts/{digest}/tags", {"name": name})
    if st not in (200, 201):
        raise SystemExit(f"harbor tag {repo}:{name} -> {digest}: {st} {body}")
