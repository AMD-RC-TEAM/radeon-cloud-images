#!/usr/bin/env python3
"""Download one GitHub source snapshot at a full commit, with retries."""

import re
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: fetch_src.py <owner/repo> <40-hex commit> <destination>")
    repo, commit, target = sys.argv[1:]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SystemExit("expected owner/repo")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit("expected a full commit")

    dest = Path(target)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
    for attempt in range(1, 6):
        try:
            with tempfile.TemporaryDirectory(prefix="src-", dir=dest.parent) as temporary:
                archive = Path(temporary) / "source.tar.gz"
                request = urllib.request.Request(url, headers={"User-Agent": "radeon-cloud-image-build/1.0"})
                with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
                    shutil.copyfileobj(response, output, 8 * 2**20)
                with tarfile.open(archive) as source:
                    root = source.getmembers()[0].name.split("/", 1)[0]
                    source.extractall(temporary, filter="tar")
                if dest.is_dir() and not any(dest.iterdir()):
                    dest.rmdir()  # A Git submodule may be represented by an empty directory.
                Path(temporary, root).rename(dest)
            print(f"{repo}@{commit[:12]} -> {dest}")
            return
        except Exception as error:  # Retry the build cluster's intermittent GitHub connection failures.
            print(f"{repo}@{commit[:12]} attempt {attempt} failed: {error}", flush=True)
            if attempt < 5:
                time.sleep(15)
    raise SystemExit(f"could not download {repo}@{commit}")


if __name__ == "__main__":
    main()
