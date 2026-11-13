"""Download a pinned file at build time, with retries (connections to github.com from the build cluster drop
intermittently), and check its sha256 when one is given.

    python3 fetch_src.py tar <owner/repo> <40-hex commit> <dest dir>    # source tarball from codeload.github.com
    python3 fetch_src.py file <url> <sha256> <dest file>
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
if kind == "tar":
    repo, commit, dest = sys.argv[2:5]
    assert re.fullmatch(r"[0-9a-f]{40}", commit), "pin a full commit"
    data = get(f"https://codeload.github.com/{repo}/tar.gz/{commit}")
    parent = os.path.dirname(dest.rstrip("/")) or "."
    os.makedirs(parent, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        root = t.getnames()[0].split("/")[0]
        t.extractall(parent, filter="data")
    os.rename(os.path.join(parent, root), dest)
    print(f"{repo}@{commit[:12]}: {len(data)} bytes -> {dest}")
elif kind == "file":
    url, sha, dest = sys.argv[2:5]
    data = get(url)
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        sys.exit(f"sha256 mismatch for {url}: {got}")
    with open(dest, "wb") as f:
        f.write(data)
    print(f"{url}: {len(data)} bytes, sha256 ok -> {dest}")
else:
    sys.exit(__doc__)
