"""Download the pinned Ollama release archives at build time, with retries (connections to github.com from the build
cluster drop intermittently), check their SHA-256 and extract them into /usr (the layout of Ollama's manual Linux
install: the base package first, then the AMD ROCm package on top).

Decompression uses the zstd command if the image has it, otherwise the python zstandard package (installed by
add_zstd.sh as a fallback). Extraction is done by tar.

    python3 fetch_ollama.py <version, e.g. 0.40.18> <sha256 of ollama-linux-amd64.tar.zst> <sha256 of ollama-linux-amd64-rocm.tar.zst>
"""
import hashlib, os, re, shutil, subprocess, sys, time, urllib.request

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


def extract(archive, dest="/usr"):
    tar = subprocess.Popen(["tar", "-x", "-C", dest], stdin=subprocess.PIPE)
    if shutil.which("zstd"):
        dec = subprocess.Popen(["zstd", "-dc", archive], stdout=subprocess.PIPE)
        shutil.copyfileobj(dec.stdout, tar.stdin)
        dec.stdout.close()
        dec_rc = dec.wait()
    else:
        import zstandard  # installed by add_zstd.sh when no zstd command is available
        with open(archive, "rb") as f, zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True) as r:
            shutil.copyfileobj(r, tar.stdin)
        dec_rc = 0
    tar.stdin.close()
    tar_rc = tar.wait()
    if dec_rc or tar_rc:
        sys.exit(f"extracting {archive} failed: decompressor exit {dec_rc}, tar exit {tar_rc}")


if len(sys.argv) != 4:
    sys.exit(__doc__)
version, sha_base, sha_rocm = sys.argv[1:4]
assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), "pin a full release version"
for name, sha in (("ollama-linux-amd64", sha_base), ("ollama-linux-amd64-rocm", sha_rocm)):
    assert re.fullmatch(r"[0-9a-f]{64}", sha), f"pin the full sha256 of {name}"
    dest = f"/tmp/{name}.tar.zst"
    download(URL.format(version=version, name=name), dest, sha)
    extract(dest)
    os.remove(dest)
    print(f"{name} v{version}: extracted into /usr", flush=True)
