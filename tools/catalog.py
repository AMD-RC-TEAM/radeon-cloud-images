"""RC catalog client: find the stable row, refuse if a template points at it, then probe + adopt the Harbor alias.

Token: a scoped operator token per site (GT / Global / China) allowed only
GET /api/admin/images, GET /api/admin/templates, POST /api/admin/images/{image_id}/harbor,
POST /api/admin/images/{image_id}/harbor/adopt. Read from $CATALOG_TOKEN_FILE (k8s Secret mount), never logged.
"""
import json, os, sys, urllib.error, urllib.request

SITES = {  # base URLs of each site's manager API, as seen from the runner (in-cluster)
    "gt": os.environ.get("CATALOG_URL_GT", ""),
    "global": os.environ.get("CATALOG_URL_GLOBAL", ""),
    "china": os.environ.get("CATALOG_URL_CHINA", ""),
}


def _call(site, method, path, body=None):
    tok = open(os.environ["CATALOG_TOKEN_DIR"] + f"/{site}").read().strip()
    req = urllib.request.Request(SITES[site].rstrip("/") + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "Accept": "application/json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace")


def _rows(payload):
    return payload.get("images", payload) if isinstance(payload, dict) else payload


def stable_row(site, row_name):
    st, body = _call(site, "GET", "/api/admin/images")
    if st != 200:
        raise SystemExit(f"[{site}] list images: {st} {body}")
    hits = [r for r in _rows(body) if r.get("name") == row_name or str(r.get("id")) == str(row_name)]
    if len(hits) != 1:
        raise SystemExit(f"[{site}] stable row '{row_name}': {len(hits)} matches")
    return hits[0]


def templates_using(site, row):
    st, body = _call(site, "GET", "/api/admin/templates")
    if st != 200:
        raise SystemExit(f"[{site}] list templates: {st} {body}")
    tpls = body.get("templates", body) if isinstance(body, dict) else body
    keys = {str(row.get("id")), str(row.get("image_key") or ""), str(row.get("name") or "")} - {""}
    return [t.get("id") for t in tpls if str(t.get("image") or t.get("image_id") or "") in keys]


def adopt(site, row_name, want_digest):
    row = stable_row(site, row_name)
    used = templates_using(site, row)
    if used:
        raise SystemExit(f"[{site}] refusing: templates {used} point at stable row '{row_name}'")
    st, body = _call(site, "POST", f"/api/admin/images/{row['id']}/harbor")
    if st != 200:
        raise SystemExit(f"[{site}] harbor probe: {st} {body}")
    if str(body.get("harbor_digest") or body.get("digest") or "") == want_digest:
        return "already current"
    st, body = _call(site, "POST", f"/api/admin/images/{row['id']}/harbor/adopt")
    if st != 200:
        raise SystemExit(f"[{site}] adopt: {st} {body}")
    got = str(body.get("harbor_digest") or body.get("digest") or "")
    if got and got != want_digest:
        raise SystemExit(f"[{site}] adopted {got}, expected {want_digest}")
    return "adopted"


if __name__ == "__main__":
    site, row_name, digest = sys.argv[1:4]
    print(f"[{site}] {row_name}: {adopt(site, row_name, digest)}")
