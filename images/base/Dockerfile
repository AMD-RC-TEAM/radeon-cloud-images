# OneClick Base with GitHub acceleration (D-20261112-23/-47): ROCm 7.2.1, PyTorch 2.9.1, vLLM 0.16.1, JupyterLab and OpenCode.
# Brought into the pipeline as-is (11-13) as FROM-only. Since 11-19 it also bakes in openssh-server (add_openssh.sh),
# so it is built and rc/base:rc-current moves to the built digest. A newer stack (newer vLLM/ROCm) is a later upgrade through a PR like any other image.
FROM crpi-xhg6joi134vrkpzq.cn-shanghai.personal.cr.aliyuncs.com/vivienfanghua/amd-oneclick-base:git-proxy-test-20260528-1125@sha256:5e0585a69e49365bfe6f88f45c6e680f7fa4f4d3d75c2c5149a483950208bfa3

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash

# OpenSSH server baked in, so Radeon Cloud's SSH setup finds sshd and skips its launch-time apt install
# (which depends on the Ubuntu archive being fast from the cluster). Host keys are generated per instance.
ARG APT_MIRROR=mirrors.aliyun.com
COPY add_openssh.sh /tmp/add_openssh.sh
RUN sh /tmp/add_openssh.sh && rm -f /tmp/add_openssh.sh
