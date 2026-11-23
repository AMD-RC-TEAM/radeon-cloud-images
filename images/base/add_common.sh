#!/bin/sh
# Common tools for the general-purpose Base image (a2, D-20261123-06): vim from the distribution, and a small pinned
# set of Python packages users of the previous Base had at hand (Hugging Face Hub with the `hf` CLI, transformers,
# accelerate, datasets, scikit-learn, ipywidgets). Like add_jupyterlab.sh, every installed distribution is pinned as
# a constraint, so if one of these needed a different version of anything already in the image (torch, numpy, ...),
# the build fails here instead of changing it.
set -eu
PY=$(command -v python3)

# vim, from the distribution source only (APT_MIRROR as in add_openssh.sh).
src=/etc/apt/sources.list
[ -r /etc/apt/sources.list.d/ubuntu.sources ] && src=/etc/apt/sources.list.d/ubuntu.sources
tmpd=$(mktemp -d)
tmp="$tmpd/$(basename "$src")"
cp "$src" "$tmp"
if [ -n "${APT_MIRROR:-}" ]; then
    sed -i -e "s@//[a-z.]*archive.ubuntu.com@//${APT_MIRROR}@g" -e "s@//security.ubuntu.com@//${APT_MIRROR}@g" "$tmp"
fi
opts="-o Dir::Etc::sourcelist=$tmp -o Dir::Etc::sourceparts=-"
DEBIAN_FRONTEND=noninteractive apt-get $opts update
DEBIAN_FRONTEND=noninteractive apt-get $opts install -y --no-install-recommends vim
rm -rf /var/lib/apt/lists/* "$tmpd"

"$PY" -m pip freeze --all | grep -E '^[A-Za-z0-9_.-]+==' > /tmp/rc-constraints.txt || true
"$PY" -m pip install --no-cache-dir -c /tmp/rc-constraints.txt \
    'huggingface_hub==2.4.0' 'transformers==5.24.0' 'accelerate==1.16.0' 'datasets==5.2.0' \
    'scikit-learn==1.9.1' 'ipywidgets==8.1.9'
rm -f /tmp/rc-constraints.txt
"$PY" -m pip check
command -v hf vim
