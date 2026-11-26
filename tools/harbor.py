"""Minimal Harbor v2 API client (pull/API host is internal; credentials come from a docker config file)."""
import base64, json, os, urllib.error, urllib.parse, urllib.request

# The registry addresses are not in this public repository: CI passes them as secrets (RC_REGISTRY_PULL / _PUSH,
# each "<host:port>/<project>"). The API is served on the pull host unless HARBOR_API says otherwise.
REGISTRY_HOSTS = [r.split("/")[0] for r in (os.environ.get("RC_REGISTRY_PULL", ""), os.environ.get("RC_REGISTRY_PUSH", "")) if r]
API = os.environ.get("HARBOR_API") or (f"http://{REGISTRY_HOSTS[0]}" if REGISTRY_HOSTS else "")
PROJECT = os.environ.get("HARBOR_PROJECT", "radeon-cloud-global")


def _auth():
    cfg = json.load(open(os.path.join(os.environ.get("DOCKER_CONFIG", os.path.expanduser("~/.docker")), "config.json")))
    for host, v in cfg.get("auths", {}).items():
        if host.split("://")[-1] in REGISTRY_HOSTS:
            return v.get("auth") or base64.b64encode(f"{v['username']}:{v['password']}".encode()).decode()
    raise SystemExit("no Harbor credentials in docker config")


def call(method, path, body=None):
    if not API:
        raise SystemExit("RC_REGISTRY_PULL (or HARBOR_API) is not set: the registry address comes from CI secrets")
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
