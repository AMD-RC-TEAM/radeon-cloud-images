"""Download the pinned Ollama release archives at build time, with retries (connections to github.com from the build
cluster drop intermittently), check their SHA-256 and extract them into /usr (the layout of Ollama's manual Linux
install: the base package first, then the AMD ROCm package on top). Needs `tar` with zstd support.

    python3 fetch_ollama.py <version, e.g. 0.40.18> <sha256 of ollama-linux-amd64.tar.zst> <sha256 of ollama-linux-amd64-rocm.tar.zst>
"""
import hashlib, os, re, subprocess, sys, time, urllib.request

URL = "https://github.com/ollama/ollama/releases/download/v{version}/{name}.tar.zst"


def download(url, dest, sha256):
    for attempt in range(6):
        try:
            h = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=180) as r, open(dest, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    h.update(chunk)
            if h.hexdigest() != sha256:
                raise ValueError(f"sha256 mismatch: got {h.hexdigest()}, want {sha256}")
            return
        except Exception as e:  # noqa: BLE001 -- retry any network error or a truncated download
            print(f"attempt {attempt + 1} for {url} failed: {e}", flush=True)
            time.sleep(20)
    sys.exit(f"could not download {url}")


if len(sys.argv) != 4:
    sys.exit(__doc__)
version, sha_base, sha_rocm = sys.argv[1:4]
assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), "pin a full release version"
for name, sha in (("ollama-linux-amd64", sha_base), ("ollama-linux-amd64-rocm", sha_rocm)):
    assert re.fullmatch(r"[0-9a-f]{64}", sha), f"pin the full sha256 of {name}"
    dest = f"/tmp/{name}.tar.zst"
    download(URL.format(version=version, name=name), dest, sha)
    subprocess.run(["tar", "--zstd", "-x", "-C", "/usr", "-f", dest], check=True)
    os.remove(dest)
    print(f"{name} v{version}: extracted into /usr", flush=True)
