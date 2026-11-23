# Base: a general-purpose ROCm + PyTorch + JupyterLab environment (owner D-20261123-06). The public upstream image,
# pinned by digest; the pipeline mirrors it into Harbor and builds/smokes from there. No vLLM (use the vLLM rows),
# no Node/Rust/OpenCode. Python and PyTorch live in /opt/venv, first on PATH, as in the previous Base.
FROM docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# OpenSSH server baked in, so Radeon Cloud's SSH setup finds sshd and skips its launch-time apt install
# (which depends on the Ubuntu archive being fast from the cluster). Host keys are generated per instance.
ARG APT_MIRROR=mirrors.aliyun.com
COPY add_openssh.sh /tmp/add_openssh.sh
RUN sh /tmp/add_openssh.sh && rm -f /tmp/add_openssh.sh

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# Common tools users of the previous Base had: vim, and pinned huggingface_hub (`hf` CLI), transformers, accelerate,
# datasets, scikit-learn and ipywidgets, installed without changing anything already in the image (add_common.sh).
COPY add_common.sh /tmp/add_common.sh
RUN sh /tmp/add_common.sh && rm -f /tmp/add_common.sh

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash

# Keep the image toolchain environment (PATH, LD_LIBRARY_PATH, ROCm settings) in SSH sessions; see keep_image_env.sh. Last step: after every ENV.
COPY keep_image_env.sh /tmp/keep_image_env.sh
RUN sh /tmp/keep_image_env.sh && rm -f /tmp/keep_image_env.sh
