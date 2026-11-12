"""Download and unpack the SGLang source tarball for a release tag (build-time only).

    python3 fetch_sglang_src.py <version> <dest>

codeload.github.com is reachable from the build cluster; the request is retried because single connections
to github.com from there drop intermittently.
"""
import io, os, sys, tarfile, time, urllib.request

version, dest = sys.argv[1], sys.argv[2]
url = f"https://codeload.github.com/sgl-project/sglang/tar.gz/refs/tags/v{version}"
data = None
for attempt in range(6):
    try:
        data = urllib.request.urlopen(url, timeout=120).read()
        break
    except Exception as e:  # noqa: BLE001 -- retry any network error
        print(f"attempt {attempt + 1} failed: {e}", flush=True)
        time.sleep(20)
if data is None:
    sys.exit(f"could not download {url}")
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    root = t.getnames()[0].split("/")[0]
    t.extractall(os.path.dirname(dest), filter="data")
os.rename(os.path.join(os.path.dirname(dest), root), dest)
print(f"sglang {version} source: {len(data)} bytes -> {dest}")
