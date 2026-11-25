#!/bin/sh
# Make zstd decompression available for fetch_ollama.py, which unpacks Ollama's .tar.zst release archives.
# Tries these in order and stops at the first that works:
#   1. zstd already in the image
#   2. apt zstd through the APT_MIRROR rewrite (same as add_openssh.sh; the Ubuntu archive is slow from the cluster)
#   3. apt zstd from the image's own sources (in case the mirror is down or lacks the package)
#   4. pip zstandard (pure Python, no system binary; fetch_ollama.py uses it when there is no zstd command)
# zstd installed by steps 2-3 stays in the image (small and handy for users).
set -u

if command -v zstd >/dev/null 2>&1; then
    echo "zstd already present: $(zstd --version)"; exit 0
fi

. /etc/os-release
case "${ID:-} ${ID_LIKE:-}" in
    *ubuntu*|*debian*) ;;
    *) echo "add_zstd.sh: unsupported base OS ${ID:-unknown} for apt" >&2 ;;
esac

# apt_zstd mirror|stock: returns 0 if the zstd package was installed.
apt_zstd() {
    src=/etc/apt/sources.list
    [ -r /etc/apt/sources.list.d/ubuntu.sources ] && src=/etc/apt/sources.list.d/ubuntu.sources
    [ -r /etc/apt/sources.list.d/debian.sources ] && src=/etc/apt/sources.list.d/debian.sources
    # Keep the file name: apt parses deb822 (*.sources) and one-line (*.list) formats by extension.
    tmpd=$(mktemp -d)
    tmp="$tmpd/$(basename "$src")"
    cp "$src" "$tmp"
    if [ "$1" = mirror ] && [ -n "${APT_MIRROR:-}" ]; then
        sed -i -e "s@//[a-z.]*archive.ubuntu.com@//${APT_MIRROR}@g" -e "s@//security.ubuntu.com@//${APT_MIRROR}@g" \
            -e "s@//deb.debian.org@//${APT_MIRROR}@g" "$tmp"
    fi
    created_policy=0
    if [ ! -e /usr/sbin/policy-rc.d ]; then
        printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod 755 /usr/sbin/policy-rc.d && created_policy=1
    fi
    export DEBIAN_FRONTEND=noninteractive
    opts="-o Dir::Etc::sourcelist=$tmp -o Dir::Etc::sourceparts=-"
    apt-get $opts update && apt-get $opts install -y --no-install-recommends zstd
    rc=$?
    rm -rf /var/lib/apt/lists/* "$tmpd"
    [ "$created_policy" = 1 ] && rm -f /usr/sbin/policy-rc.d
    return $rc
}

if apt_zstd mirror; then
    echo "zstd installed from the APT_MIRROR archive"
elif apt_zstd stock; then
    echo "zstd installed from the image's own apt sources"
else
    echo "add_zstd.sh: apt could not install zstd; trying pip" >&2
fi

if command -v zstd >/dev/null 2>&1; then
    echo "zstd: $(zstd --version)"; exit 0
fi

# pip fallback: the zstandard package decompresses in Python, so no zstd command is needed.
PY=$(command -v python3 || command -v python)
if "$PY" -m pip install --no-cache-dir --no-deps 'zstandard==0.23.0' && "$PY" -c 'import zstandard' ; then
    echo "zstd command not available; fetch_ollama.py will use the python zstandard package"; exit 0
fi

echo "add_zstd.sh: no way to decompress zstd (apt mirror, apt stock and pip all failed)" >&2
exit 1
