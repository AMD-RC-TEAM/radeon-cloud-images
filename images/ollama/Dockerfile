# Ollama for Radeon PRO W7900 / W7900D (gfx1100). The public upstream image, pinned by digest; the pipeline mirrors it into Harbor and builds/smokes from there.
FROM docker.io/<org>/<image>:<tag>@sha256:<digest>

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# Ollama from its GitHub release (https://github.com/ollama/ollama/releases): ollama-linux-amd64.tar.zst and
# ollama-linux-amd64-rocm.tar.zst, extracted into /usr, pinned by version and SHA-256 (the digests GitHub shows for
# each asset). The README goes to /opt/ollama.
ARG OLLAMA_VERSION=0.40.18
ARG OLLAMA_AMD64_SHA256=b82649006cb5b54ed1237fa2d1a26a7f939a4fd03150033759acbff7ff315adf
ARG OLLAMA_ROCM_SHA256=d404a0f936a69ecf7904f228f68cf65021fdf45e4b66db3fb9c8603abd206447
COPY fetch_ollama.py README.md /tmp/rc/
RUN python3 /tmp/rc/fetch_ollama.py ${OLLAMA_VERSION} ${OLLAMA_AMD64_SHA256} ${OLLAMA_ROCM_SHA256} \
 && install -D -m 644 /tmp/rc/README.md /opt/ollama/README.md \
 && rm -rf /tmp/rc

# OpenSSH server baked in, so Radeon Cloud's SSH setup finds sshd and skips its launch-time apt install
# (which depends on the Ubuntu archive being fast from the cluster). Host keys are generated per instance.
ARG APT_MIRROR=mirrors.aliyun.com
COPY add_openssh.sh /tmp/add_openssh.sh
RUN sh /tmp/add_openssh.sh && rm -f /tmp/add_openssh.sh

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash
