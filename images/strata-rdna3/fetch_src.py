"""Download a pinned GitHub source tarball at build time, with retries and a SHA-256 check.

    python3 fetch_src.py tar <owner/repo> <40-hex commit> <sha256> <dest dir>

codeload.github.com is reachable from the build cluster; the request is retried because
single connections to github.com from there drop intermittently.
"""
import hashlib, io, os, re, sys, tarfile, time, urllib.request


def get(url):
    for attempt in range(6):
        try:
            return urllib.request.urlopen(url, timeout=180).read()
        except Exception as e:  # noqa: BLE001 -- retry any network error
            print(f"attempt {attempt + 1} for {url} failed: {e}", flush=True)
            time.sleep(20)
    sys.exit(f"could not download {url}")


kind = sys.argv[1]
if kind != "tar":
    sys.exit(__doc__)
repo, commit, expect, dest = sys.argv[2:6]
assert re.fullmatch(r"[0-9a-f]{40}", commit), "pin a full commit"
assert re.fullmatch(r"[0-9a-f]{64}", expect), "pin a sha256"
data = get(f"https://codeload.github.com/{repo}/tar.gz/{commit}")
got = hashlib.sha256(data).hexdigest()
if got != expect:
    sys.exit(f"{repo}@{commit[:12]} sha256 {got} != {expect}")
parent = os.path.dirname(dest.rstrip("/")) or "."
os.makedirs(parent, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    root = t.getnames()[0].split("/")[0]
    t.extractall(parent, filter="data")
os.rename(os.path.join(parent, root), dest)
print(f"{repo}@{commit[:12]}: {len(data)} bytes sha256 {got} -> {dest}")
