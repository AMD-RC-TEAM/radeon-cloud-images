#!/bin/sh
# Bake a JupyterLab that passes Radeon Cloud's launch-time check into this image, without changing anything that
# is already installed. Without it, every launch pip-installs JupyterLab in the prepare-notebook-runtime step
# (18-188 s per launch, measured 11-13). The check wants: `jupyter` on PATH, Python 3.10-3.12,
# jupyter_server >=2.14,<3 and jupyterlab >=4.2,<5. The versions match the Base image.
# Every installed distribution is pinned as a constraint, so if JupyterLab needed a different version of
# anything already in the image, the build fails here instead of changing it silently. The smoke compares
# /opt/pip-freeze-before.txt with the final freeze.
set -eu
PY=$(command -v python3 || command -v python)
"$PY" -m pip freeze --all > /opt/pip-freeze-before.txt
grep -E '^[A-Za-z0-9_.-]+==' /opt/pip-freeze-before.txt > /tmp/rc-constraints.txt || true
"$PY" -m pip install --no-cache-dir -c /tmp/rc-constraints.txt 'jupyter_server==2.17.0' 'jupyterlab==4.5.6'
rm -f /tmp/rc-constraints.txt
command -v jupyter
