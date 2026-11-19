#!/usr/bin/env python3
"""Catalog step of the image pipeline (D-20261112-33), run by rc-ops on standby46, not in CI.

For each stable row in catalog-rows.json: refuse if any template references the row, then
POST /api/admin/images/{id}/harbor (re-inspect the rc-current alias). If the probe reports drift,
POST .../harbor/adopt and read the row back. Uses the owner's Admin session cookie jar, read-only
(never written, never printed). Cookie writes need an exact Origin and a Referer under /admin.

  catalog_sync.py [--site gt] [--dry-run]     # dry-run: GETs only
Exit 0 = nothing to do or all adopted; 1 = a row failed or was refused; 2 = session/setup problem.
"""
import argparse, datetime as dt, http.cookiejar, json, os, re, subprocess, sys, tempfile, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.expanduser("~/hk-dx/secrets")
SITES = {  # base URL, cookie jar
    "gt": ("https://radeon-global-test.anruicloud.com", os.path.join(SECRETS, "admin-gt.cookie")),
    "global": ("https://radeon-global.anruicloud.com", os.path.join(SECRETS, "admin-global.cookie")),
    "china": ("https://developer.amd.com.cn/radeon", os.path.join(SECRETS, "admin-cn.cookie")),
    # rc-ux 11-14 (RULES 14): /radeon2 is China's rehearsal copy, so its stable rows follow rc-current too.
    "radeon2": ("https://developer.amd.com.cn/radeon2", os.path.join(SECRETS, "admin-radeon2.cookie")),
}
STATUS = os.path.expanduser("~/hk-dx/rc/capacity/STATUS.md")
# Production gate (owner D-20261112-37): a digest reaches Global/China only after an automatic launch check on GT
# passed for that exact digest. The PR Approve in radeon-cloud-images is the only human gate.
GT_PASSED = os.path.join(HERE, "state-gt-launch-passed.json")
PROD_HOLD = os.path.join(HERE, "state-prod-hold.json")
PROD_ADOPTED = os.path.join(HERE, "state-prod-adopted.json")  # {"<category>": {digest, prev, at, verdict}}: +1h regression check
Q_SH = os.path.expanduser("~/hk-dx/rc/capacity/ssrf-345/tools/q.sh")           # read-only SQL on the Global manager DB via 0004
HARBOR_PY = "/home/hfang/rci-images-8Vde/tools/harbor.py"
HARBOR_CREDS = os.path.expanduser("~/hk-dx/secrets/harbor-robot-radeon-cloud-images-ci.dockerconfigjson")    # {"<category>": "reason"}: GT moves, prod sites wait   # {"<category>": {"digest": ..., "at": iso, "detail": ...}}
GT_SVC = "https://radeon-global-test.anruicloud.com/api/service"
GT_TENANT_TOKEN = os.path.join(SECRETS, "synthetic", "gt-tenant.token")
CHECK_USER = "rc-images-check"            # own Service API user, never collides with the synthetic GPU probe user
CHECK_POOL, CHECK_TEMPLATE = "one-click", "resource-16c55g1u"
FALLBACK_POOLS = ["hf"]   # GT: granted to the check user by rc-ux 11-13 (user resource label), not in the tenant pool list
IMAGES_REPO = "AMD-RC-TEAM/radeon-cloud-images"


class Session:
    def __init__(self, site):
        self.base, jar_path = SITES[site]
        self.origin = "/".join(self.base.split("/")[:3])        # scheme://host, no path
        jar = http.cookiejar.MozillaCookieJar(jar_path)
        jar.load(ignore_discard=True, ignore_expires=True)  # read only; we never save it
        self.expires = min((c.expires for c in jar if c.expires), default=None)
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(self, method, path, body=None):
        h = {"Accept": "application/json"}
        if method != "GET":
            h.update({"Origin": self.origin, "Referer": self.base + "/admin/images", "Content-Type": "application/json"})
        req = urllib.request.Request(self.base + path, method=method, headers=h,
                                     data=json.dumps(body).encode() if body is not None else (b"" if method != "GET" else None))
        try:
            with self.opener.open(req, timeout=120) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode("utf-8", "replace")[:200])
        except urllib.error.HTTPError as e:
            return e.code, e.read()[:300].decode("utf-8", "replace")


def row_of(body):
    """Probe/adopt may return the row itself or wrap it under "image"."""
    if isinstance(body, dict) and isinstance(body.get("image"), dict):
        return body["image"]
    return body if isinstance(body, dict) else {}


def digest_of(row):
    img = str(row.get("image") or "")
    return img.split("@", 1)[1] if "@sha256:" in img else str(row.get("harbor_digest") or "")


def _jread(path, default):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


def _jwrite(path, data):
    tmp = path + ".tmp"; json.dump(data, open(tmp, "w"), indent=1); os.replace(tmp, path)


def gt_launch_check(row_id):
    """Start one minimal instance on GT from catalog row `row_id` through the Service API, delete it once ready.
    Returns (verdict, detail): verdict is "pass", "fail" or "retry" (pool full / transient)."""
    import time, uuid, urllib.parse
    tok = open(GT_TENANT_TOKEN).read().strip()
    H = {"Authorization": "Bearer " + tok, "Accept": "application/json", "Content-Type": "application/json"}

    def call(method, path, params=None, body=None, timeout=120, extra=None):
        url = GT_SVC + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, method=method, headers=dict(H, **(extra or {})),
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read(); return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else {})
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"detail": raw[:200].decode("utf-8", "replace")}
        except OSError as e:
            return 0, {"detail": f"{type(e).__name__}"}

    q = {"user_name": CHECK_USER}

    def teardown():
        for _ in range(60):
            code, b = call("GET", "/notebooks/current", q)
            if code == 404 or b.get("status") in (None, "not_found"):
                return True
            call("DELETE", "/notebooks/current", q)
            time.sleep(10)
        return False

    teardown()                                   # leftover from an earlier run of this check
    # D-20261113-15: do not wait on a full one-click pool; use another pool of this tenant that has a free GPU
    # (one-click first), and record which one was used.
    code, st = call("GET", "/pools/status")
    choices = []
    for p in (st.get("pools") or []) if code == 200 else []:
        tpl = next((t for t in p.get("templates") or [] if t.get("gpu_count") == 1 and int(t.get("fit_count") or 0) > 0), None)
        if tpl:
            choices.append((p["pool_id"] != CHECK_POOL, p["pool_id"], tpl["resource_template"]))
    # /pools/status lists the tenant's pools; pools granted to the check user only (GT: hf, D-20261113-15) are
    # not listed there, so try them directly too.
    listed = {pid for _, pid, _ in choices} | {p.get("pool_id") for p in (st.get("pools") or [])}
    choices += [(True, pid, CHECK_TEMPLATE) for pid in FALLBACK_POOLS if pid not in listed]
    if not choices:
        seen = [f"{p.get('pool_id')} {p.get('free_gpus')}/{p.get('total_gpus')}" for p in (st.get("pools") or [])]
        return "retry", f"no pool with a free 1-GPU slot ({', '.join(seen) or f'pools/status {code}'})"
    t0 = time.time()
    for _, pool, rtpl in sorted(choices):
        code, b = call("POST", "/notebooks", {"uid": CHECK_USER},
                       {"user_name": CHECK_USER, "pod_type": pool, "resource_template": rtpl,
                        "image": f"production-{row_id}"}, extra={"Idempotency-Key": uuid.uuid4().hex})
        if code in (400, 403, 409, 429, 503) or "full" in json.dumps(b).lower():
            continue          # busy, or this pool is not allowed for the check user: try the next one
        break
    else:
        return "retry", f"launch {code}: every pool with a free slot refused ({', '.join(p for _, p, _ in choices)})"
    if code >= 400 or code == 0:
        return "fail", f"launch {code} on pool {pool}: {json.dumps(b, ensure_ascii=False)[:160]}"
    verdict, detail = "fail", "not ready within 15 min"
    while time.time() - t0 < 900:
        time.sleep(15)
        code, b = call("GET", "/notebooks/current", q)
        st = str(b.get("status") or "")
        if st == "ready":
            verdict, detail = "pass", f"ready in {time.time() - t0:.0f}s on pool {pool}"
            break
        if st in ("failed", "error"):
            verdict, detail = "fail", f"status {st}: {str(b.get('message') or b.get('detail') or '')[:120]}"
            break
    if not teardown():
        detail += "; WARNING teardown not confirmed"
    return verdict, detail


def templates_on(row, tpls):
    keys = {str(row.get("id")), f"production-{row.get('id')}", str(row.get("image") or ""),
            str(row.get("source_ref") or ""), str(row.get("name") or "")} - {""}
    return [t.get("id") for t in tpls if str(t.get("image") or t.get("image_id") or "") in keys]


def ensure_previous_row(s, site, cat, stable_row, images):
    """One hidden '<name> (previous)' row per category tracking rc/<cat>:rc-prev. Created with POST only."""
    src = str(stable_row.get("source_ref") or "").replace(":rc-current", ":rc-prev")
    if not src.endswith(":rc-prev"):
        return None
    for r in images:
        if str(r.get("source_ref") or "") == src:
            return r
    body = {"name": f"{stable_row.get('name')} (previous)", "source_ref": src,
            "description": f"Previous version of {stable_row.get('name')} (rc-prev), kept for rollback",
            "enabled": True, "picker_visible": False, "preheat": False}
    st, res = s.call("POST", "/api/admin/images", body)
    if st not in (200, 201):
        print(f"[{site}] {cat}: could not create previous row: {st} {str(res)[:160]}")
        return None
    print(f"[{site}] {cat}: created hidden previous row '{body['name']}'")
    return row_of(res) or None


def rows_of(payload):
    return payload.get("images", payload) if isinstance(payload, dict) else payload


def _adopt(s, site, label, rid):
    """probe + adopt on one row; returns (status, new_digest) with status in drift-adopted / no-drift / error."""
    st, probe = s.call("POST", f"/api/admin/images/{rid}/harbor")
    if st != 200:
        return "error", f"probe {st} {str(probe)[:120]}"
    if str(row_of(probe).get("harbor_status") or "") != "drift":
        return "no-drift", ""
    st, res = s.call("POST", f"/api/admin/images/{rid}/harbor/adopt")
    if st != 200:
        return "error", f"adopt {st} {str(res)[:120]}"
    st2, after = s.call("GET", "/api/admin/images")
    row = next((r for r in rows_of(after) if str(r.get("id")) == str(rid)), {}) if st2 == 200 else {}
    return "adopted", digest_of(row) or digest_of(row_of(res))



MANUAL_SEEN = os.path.join(HERE, "state-manual-rows.json")


def watch_manual_rows(site, images):
    """a2 11-13: a manager restart re-seeded a manual "AMD OneClick Base" row (China 247, picker-visible).
    Report any manual row id not seen before on a site (first run only records the baseline)."""
    seen = _jread(MANUAL_SEEN, {})
    ids = sorted(int(r["id"]) for r in images if str(r.get("source_type") or "") == "manual")
    if site in seen:
        new = [r for r in images if str(r.get("source_type") or "") == "manual" and int(r["id"]) not in seen[site]]
        for r in new:
            _status(f"New manual image row: {site} row {r['id']} '{r.get('name')}' picker_visible={r.get('picker_visible')} (possibly re-seeded by a manager restart; tell rc-ux and a2)")
    seen[site] = ids
    _jwrite(MANUAL_SEEN, seen)
    # a2 11-13: China 247 (the seeded "AMD OneClick Base") must exist and stay hidden; it absorbs the default-image seed.
    if site == "china":
        r247 = next((r for r in images if str(r.get("id")) == "247"), None)
        if r247 is None or r247.get("picker_visible") is not False:
            _status(f"China row 247 (the seeded AMD OneClick Base) is in an unexpected state: {'missing' if r247 is None else 'picker_visible=' + str(r247.get('picker_visible'))}. Hide it by hand with the guarded tool and tell a2 and rc-ux")

def _status(line):
    with open(STATUS, "a") as f:
        f.write(f"- {dt.datetime.now(dt.timezone.utc):%m-%dT%H:%MZ} [catalog_sync] {line}\n")


def sync_site(site, rows, dry):
    s = Session(site)
    if s.expires and s.expires - dt.datetime.now(dt.timezone.utc).timestamp() < 3 * 86400:
        print(f"[{site}] WARNING admin session expires {dt.datetime.fromtimestamp(s.expires, dt.timezone.utc):%m-%d %H:%MZ}: ask a2 to renew")
    st, images = s.call("GET", "/api/admin/images")
    if st != 200:
        print(f"[{site}] list images: {st} {images}"); return 2
    st, tpls = s.call("GET", "/api/admin/templates")
    if st != 200:
        print(f"[{site}] list templates: {st} {tpls}"); return 2
    tpls = tpls.get("templates", tpls) if isinstance(tpls, dict) else tpls
    if not dry:
        watch_manual_rows(site, rows_of(images))
    images = rows_of(images)
    by_id = {str(r.get("id")): r for r in images}
    passed = _jread(GT_PASSED, {})
    hold = _jread(PROD_HOLD, {})
    rc = 0
    for cat, rid in rows.items():
        row = by_id.get(str(rid))
        if not row:
            print(f"[{site}] {cat}: row {rid} not found"); rc = 1; continue
        used = templates_on(row, tpls)
        if used:
            # D-39: a template that references the stable row itself (id, production-<id>, name, source_ref) blocks the
            # move. A template that only pins the row's current DIGEST keeps launching that digest as long as another
            # enabled row carries it (a2/rc-ux 11-14, D-20261114-02): make the hidden "(previous)" row hold the digest
            # FIRST, confirm the coverage, and only then move the stable row. Otherwise refuse, as before.
            cur_img = str(row.get("image") or "")
            by_row = [t.get("id") for t in tpls if str(t.get("image") or t.get("image_id") or "") in
                      ({str(rid), f"production-{rid}", str(row.get("source_ref") or ""), str(row.get("name") or "")} - {""})]
            if by_row or not cur_img:
                print(f"[{site}] {cat}: REFUSED, templates {by_row[:10] or used[:10]} reference stable row {rid}"); rc = 1; continue
            covered = lambda imgs: [r.get("id") for r in imgs if str(r.get("id")) != str(rid) and r.get("enabled") is not False
                                    and str(r.get("image") or "") == cur_img]
            cov = covered(images)
            if not cov and dry:
                print(f"[{site}] {cat}: templates {used[:10]} pin digest {digest_of(row)[:19]}; would make the (previous) row carry it first (dry run)"); continue
            if not cov:
                prev = ensure_previous_row(s, site, cat, row, images)
                if prev:
                    pst, pnew = _adopt(s, site, cat + " (previous)", prev.get("id"))
                    print(f"[{site}] {cat}: previous row {prev.get('id')} before moving the stable row: {pst} {pnew[:19]}")
                st2, fresh = s.call("GET", "/api/admin/images")
                if st2 == 200:
                    images = rows_of(fresh); by_id = {str(r.get("id")): r for r in images}
                cov = covered(images)
            if not cov:
                print(f"[{site}] {cat}: REFUSED, templates {used[:10]} pin digest {digest_of(row)[:19]} and no other enabled row carries it yet"); rc = 1; continue
            print(f"[{site}] {cat}: templates {used[:10]} pin digest {digest_of(row)[:19]}, covered by row(s) {cov}; stable row may move")
        if dry:
            print(f"[{site}] {cat}: row {rid} '{row.get('name')}' digest={digest_of(row)[:19]} status={row.get('harbor_status')} "
                  f"gt_passed={passed.get(cat, {}).get('digest', '')[:19]} (dry run)")
            continue
        h = hold.get(cat)   # "reason" holds every production site; {"reason": ..., "sites": [...]} holds only those
        if site != "gt" and h and (isinstance(h, str) or site in h.get("sites", [])):
            print(f"[{site}] {cat}: held for production ({h if isinstance(h, str) else h.get('reason')})"); continue
        if site != "gt":
            st, probe = s.call("POST", f"/api/admin/images/{rid}/harbor")
            if st != 200:
                print(f"[{site}] {cat}: probe {st} {str(probe)[:120]}"); rc = 1; continue
            pr = row_of(probe)
            if str(pr.get("harbor_status") or "") != "drift":
                print(f"[{site}] {cat}: no drift"); continue
            want = str(pr.get("harbor_remote_digest") or "")
            want = want.split("@", 1)[1] if "@" in want else want   # Admin reports <repo>@sha256:...; GT_PASSED keeps the bare digest
            if passed.get(cat, {}).get("digest") != want:
                print(f"[{site}] {cat}: drift to {want[:19]} held until the GT launch check passes for it"); continue
            status, new = _adopt(s, site, cat, rid)
        else:
            status, new = _adopt(s, site, cat, rid)
        if status == "error":
            print(f"[{site}] {cat}: {new}"); rc = 1; continue
        if status == "adopted":
            print(f"[{site}] {cat}: ADOPTED row {rid} -> {new[:19]}")
            if site != "gt":
                adopted = _jread(PROD_ADOPTED, {})
                rec = adopted.get(cat, {})
                if rec.get("digest") != new:
                    adopted[cat] = {"digest": new, "prev": digest_of(row), "sites": [site], "verdict": None,
                                    "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
                elif site not in rec.get("sites", []):
                    rec.setdefault("sites", []).append(site)
                _jwrite(PROD_ADOPTED, adopted)
            _status(f"{site} {cat}: stable row {rid} adopted new digest {new[:19]}")
            prev = ensure_previous_row(s, site, cat, row, images)
            if prev:
                if templates_on(prev, tpls):
                    print(f"[{site}] {cat}: previous row {prev.get('id')} is referenced by templates; left as it is")
                else:
                    pst, pnew = _adopt(s, site, cat + " (previous)", prev.get("id"))
                    print(f"[{site}] {cat}: previous row {prev.get('id')}: {pst} {pnew[:19]}")
        if site == "gt":
            cur = new if status == "adopted" else digest_of(row)
            if cur and passed.get(cat, {}).get("digest") != cur:
                verdict, detail = gt_launch_check(rid)
                print(f"[gt] {cat}: launch check on {cur[:19]}: {verdict} ({detail})")
                if verdict == "pass":
                    passed[cat] = {"digest": cur, "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "detail": detail}
                    _jwrite(GT_PASSED, passed)
                    _status(f"gt {cat}: launch check passed ({cur[:19]}, {detail}); production may follow")
                elif verdict == "fail":
                    rc = 1
                    _status(f"gt {cat}: launch check FAILED ({cur[:19]}: {detail}); production does not follow")
    return rc


def launch_stats(digest, start, end):
    """(ok, failed) launch jobs for an image digest in [start, end); capacity shortages and cancels are not image failures."""
    import re, subprocess
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest or ""):
        return None
    sql = ("select count(*) filter (where status = 'succeeded'), "
           "count(*) filter (where status = 'failed' and coalesce(error_code, '') <> 'resource_capacity_insufficient') "
           f"from launch_jobs where created_at::timestamptz >= '{start}' and created_at::timestamptz < '{end}' "
           f"and payload_json::text like '%{digest}%';\n")
    r = subprocess.run([Q_SH, "global"], input=sql, capture_output=True, text=True, timeout=240)
    try:
        ok, bad = r.stdout.strip().splitlines()[-1].split("\t")
        return int(ok), int(bad)
    except (ValueError, IndexError):
        print(f"launch_stats: query failed: {r.stderr.strip()[-200:]}")
        return None


def harbor_rollback(cat, good, bad):
    """rc/<cat>:rc-current -> good, bad gets rc-rolled-back. Harbor's API is only reachable from inside Wuxi (0004)."""
    import subprocess
    d = subprocess.run(["ssh", "-o", "BatchMode=yes", "0004", "mktemp -d /root/rcops-rollback-XXXX"],
                       capture_output=True, text=True, timeout=60).stdout.strip()
    if not d.startswith("/root/rcops-rollback-"):
        return False, "no temp dir on 0004"
    try:
        subprocess.run(["scp", "-q", HARBOR_PY, f"0004:{d}/harbor.py"], check=True, timeout=120)
        subprocess.run(["scp", "-q", HARBOR_CREDS, f"0004:{d}/config.json"], check=True, timeout=120)
        code = (f"import sys; sys.path.insert(0, {d!r}); import harbor\n"
                f"harbor.tag('rc/{cat}', {bad!r}, 'rc-rolled-back')\n"
                f"harbor.tag('rc/{cat}', {good!r}, 'rc-current')\n"
                f"print('rc-current', harbor.artifact('rc/{cat}', 'rc-current')['digest'])\n")
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "0004", f"chmod 600 {d}/config.json; DOCKER_CONFIG={d} python3 -I -"],
                           input=code, capture_output=True, text=True, timeout=180)
        return (good in r.stdout), (r.stdout + r.stderr).strip()[-300:]
    finally:
        subprocess.run(["ssh", "-o", "BatchMode=yes", "0004", f"rm -rf -- {d}"], capture_output=True, timeout=60)


def feishu(text):
    sys.path.insert(0, os.path.expanduser("~/hk-dx/rc/reliability"))
    try:
        import synthetic
        return synthetic.feishu(text)
    except Exception as e:  # noqa: BLE001 -- an alert path must not break the sync
        print(f"feishu failed: {e}")
        return False


def check_regressions(dry):
    """D-37: from +1h after a production adopt, compare launch failures of the new digest with the old one's last 24 h.
    Clearly worse -> roll rc-current back to the old digest (all sites follow on the next runs) and tell Feishu."""
    adopted = _jread(PROD_ADOPTED, {})
    now = dt.datetime.now(dt.timezone.utc)
    for cat, r in adopted.items():
        if r.get("verdict"):
            continue
        at = dt.datetime.strptime(r["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        age = (now - at).total_seconds()
        if age < 3600:
            continue
        fmt = lambda t: t.strftime("%Y-%m-%d %H:%M:%S+00")
        new = launch_stats(r["digest"], fmt(at), fmt(now))
        base = launch_stats(r.get("prev", ""), fmt(at - dt.timedelta(hours=24)), fmt(at)) if r.get("prev") else (0, 0)
        if new is None or base is None:
            continue
        n, bad = sum(new), new[1]
        bn, bbad = sum(base), base[1]
        rate, brate = (bad / n if n else 0.0), (bbad / bn if bn else 0.0)
        summary = (f"{cat} {r['digest'][:19]}: {bad}/{n} failed since {r['at']} vs previous "
                   f"{(r.get('prev') or '')[:19]} {bbad}/{bn} in the 24 h before")
        print(f"[regression] {summary}")
        if n < 5:
            if age > 6 * 3600:
                r["verdict"] = "insufficient"
                _status(f"{cat}: only {n} launches in the 6 h after the production adopt, too few to judge a rollback ({summary})")
            continue
        if bad >= 3 and rate > max(2 * brate, brate + 0.10):
            if dry:
                print(f"[regression] WOULD ROLL BACK {cat} (dry run)"); continue
            ok, out = harbor_rollback(cat, r["prev"], r["digest"])
            r["verdict"] = "rolled-back" if ok else "rollback-failed"
            if ok:
                passed = _jread(GT_PASSED, {})
                passed[cat] = {"digest": r["prev"], "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "detail": "rollback target (was live in production)"}
                _jwrite(GT_PASSED, passed)
            msg = (f"[RC image auto-rollback] {cat}: launch failure rate got worse after the production adopt ({summary}). "
                   + (f"rc/{cat}:rc-current is rolled back to {r['prev'][:19]}; every site follows on its next sync; the new digest is tagged rc-rolled-back."
                      if ok else f"Rollback FAILED, needs a person: {out}"))
            _status(msg); feishu(msg)
        else:
            r["verdict"] = "ok"
            _status(f"{cat}: production +1h check passed ({summary})")
    if not dry:
        _jwrite(PROD_ADOPTED, adopted)


def daily_report(cfg):
    """D-39: name every template that points at a stable row (those rows move with the pipeline)."""
    lines = []
    for site in [x for x in ("gt", "radeon2", "global", "china") if x in cfg and x in SITES]:
        s = Session(site)
        st, images = s.call("GET", "/api/admin/images"); st2, tpls = s.call("GET", "/api/admin/templates")
        if st != 200 or st2 != 200:
            lines.append(f"- {site}: could not read the catalog ({st}/{st2})"); continue
        tpls = tpls.get("templates", tpls) if isinstance(tpls, dict) else tpls
        by_id = {str(r.get("id")): r for r in rows_of(images)}
        for cat, rid in cfg[site].items():
            row = by_id.get(str(rid))
            if not row:
                continue
            for tid in templates_on(row, tpls):
                t = next((x for x in tpls if x.get("id") == tid), {})
                lines.append(f"- {site}: template {tid} \"{str(t.get('title') or '')[:60]}\" (owner {t.get('owner_user_id') or 'built-in'}) "
                             f"points at the stable row {rid} \"{row.get('name')}\". Point it at a fixed-version row instead.")
    return lines


# ---- D-20261114-08: picker descriptions carry the key software versions -------------------------------------------
VERSIONS_CACHE = os.path.join(HERE, "state-versions.json")     # {"sha256:...": {"image": ..., "versions": {...}}}
META_RUN = os.path.join(HERE, "catalog-metadata", "meta_run.sh")
# Sites where every run keeps descriptions in step (rehearsed first on gt/radeon2, RULES 14; then global/china).
DESC_SITES = os.path.join(HERE, "state-description-sites.json")
VERSIONS_LINE = re.compile(r"RC-VERSIONS-OF (sha256:[0-9a-f]{64}) (\{.*\})")


def versions_for(digests):
    """Versions per digest from the release / versions-probe run logs (cached locally; runs are read-only)."""
    cache = _jread(VERSIONS_CACHE, {})
    want = {d for d in digests if d and d not in cache}
    if want:
        for wf in ("release.yml", "versions-probe.yml"):
            r = subprocess.run(["gh", "run", "list", "-R", IMAGES_REPO, "-w", wf, "-L", "40", "--json",
                                "databaseId,conclusion", "-q", ".[]|select(.conclusion==\"success\")|.databaseId"],
                               capture_output=True, text=True)
            for run_id in r.stdout.split():
                if not want:
                    break
                log = subprocess.run(["gh", "run", "view", run_id, "-R", IMAGES_REPO, "--log"],
                                     capture_output=True, text=True).stdout
                for d, js in VERSIONS_LINE.findall(log):
                    try:
                        cache[d] = json.loads(js)
                    except ValueError:
                        continue
                    want.discard(d)
        _jwrite(VERSIONS_CACHE, cache)
    return {d: cache[d]["versions"] for d in digests if d in cache and cache[d].get("versions")}


def described(desc, versions):
    """'<purpose> · ROCm x · Python y · ...': the purpose is whatever precedes an earlier ' · ROCm '/' · Python ' suffix."""
    purpose = re.split(r" · (?:ROCm|Python)[ \u00a0]", str(desc or ""), maxsplit=1)[0].rstrip().rstrip(".")
    purpose = PURPOSE_FIX.get(purpose, purpose)
    # Show release numbers only: "0.5.19.dev338" -> "0.5.19" (the probe JSON keeps the full string). A no-break space
    # keeps each "name version" pair on one line in the picker (rc-ux 11-14: "Unsloth / 2026.6.9" split at 375 px).
    return purpose + " · " + " · ".join(f"{k}\u00a0{re.sub(r'[.-]?dev[0-9]*$', '', str(v))}" for k, v in versions.items())


# Purpose-line corrections applied with the versions (rc-ux 11-14: OpenCode is masked in managed workspaces).
PURPOSE_FIX = {"General-purpose ROCm environment with Python, JupyterLab and OpenCode":
               "General-purpose ROCm environment with Python and JupyterLab"}


def sync_descriptions(site, rows, dry):
    """Stable rows and their '(previous)' rows: description = purpose + versions of the row's own digest.
    Only the description column, only through the guarded DB tool (meta_run.sh), only when it differs."""
    s = Session(site)
    st, images = s.call("GET", "/api/admin/images")
    if st != 200:
        print(f"[{site}] descriptions: list images {st}"); return 2
    images = rows_of(images)
    stable = {str(rid) for rid in rows.values()}
    prev_src = {str(r.get("source_ref") or "").replace(":rc-current", ":rc-prev") for r in images if str(r.get("id")) in stable}
    targets = [r for r in images if str(r.get("id")) in stable or str(r.get("source_ref") or "") in prev_src - {""}]
    vers = versions_for([digest_of(r) for r in targets])
    chg, exp, missing = [], [], []
    for r in targets:
        d = digest_of(r)
        if not d:
            continue
        if d not in vers:
            missing.append(f"{r['id']}:{d[7:19]}"); continue
        new = described(r.get("description"), vers[d])
        if new != (r.get("description") or ""):
            chg.append(("images", str(r["id"]), "description", new)); exp.append(("images", str(r["id"]), "description", r.get("description") or ""))
    if missing:
        print(f"[{site}] descriptions: no versions yet for {', '.join(missing)} (run the versions-probe workflow)")
    if not chg:
        print(f"[{site}] descriptions: up to date"); return 0
    for _, rid, _, new in chg:
        print(f"[{site}] description {rid}: {new}")
    if dry:
        return 0
    d = tempfile.mkdtemp(prefix="desc-")
    for name, lines in (("desc-changes.tsv", chg), ("desc-expect.tsv", exp)):  # meta_run keeps its own changes.tsv/expect.tsv
        with open(os.path.join(d, name), "w") as f:
            for t in lines:
                if any("\t" in x or "\n" in x for x in t):
                    raise SystemExit("tab/newline in a description")
                f.write("\t".join(t) + "\n")
    r = subprocess.run(["bash", META_RUN, site, os.path.join(d, "desc-changes.tsv"), os.path.join(d, "desc-expect.tsv")],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    ok = r.returncode == 0 and any("not ok: 0" in l for l in out)
    print(f"[{site}] descriptions: {'applied' if ok else 'FAILED'} {len(chg)} rows; " + " | ".join(out[-4:]))
    _status(f"{site} image descriptions with versions: {'updated' if ok else 'FAILED'} {len(chg)} rows ({', '.join(rid for _, rid, _, _ in chg)}) via the meta_run guarded tool" + ("" if ok else "; needs a person"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--daily", action="store_true", help="print templates that point at stable rows (D-39)")
    ap.add_argument("--descriptions-only", action="store_true", help="only the D-20261114-08 description pass")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(HERE, "catalog-rows.json")))
    if a.daily:
        lines = daily_report(cfg)
        print("\n".join(lines) if lines else "no template points at a stable row")
        return 0
    rc = 0
    if a.descriptions_only:
        for site in a.site or [x for x in ("gt", "radeon2", "global", "china") if x in cfg and x in SITES]:
            rc = max(rc, sync_descriptions(site, cfg[site], a.dry_run))
        return rc
    for site in a.site or [x for x in ("gt", "radeon2", "global", "china") if x in cfg and x in SITES]:
        rc = max(rc, sync_site(site, cfg[site], a.dry_run))
        if site in _jread(DESC_SITES, []):
            rc = max(rc, sync_descriptions(site, cfg[site], a.dry_run))
    if not a.site:
        check_regressions(a.dry_run)
    return rc


if __name__ == "__main__":
    sys.exit(main())
