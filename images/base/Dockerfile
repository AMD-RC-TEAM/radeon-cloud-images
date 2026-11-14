# OneClick Base with GitHub acceleration (D-20261112-23/-47): ROCm 7.2.1, PyTorch 2.9.1, vLLM 0.16.1, JupyterLab and OpenCode.
# Brought into the pipeline as-is (11-13): FROM-only, so the release keeps today's digest and rc/base:rc-current
# does not move. A newer stack (newer vLLM/ROCm) is a later upgrade through a PR like any other image.
FROM crpi-xhg6joi134vrkpzq.cn-shanghai.personal.cr.aliyuncs.com/vivienfanghua/amd-oneclick-base:git-proxy-test-20260528-1125@sha256:5e0585a69e49365bfe6f88f45c6e680f7fa4f4d3d75c2c5149a483950208bfa3

# First-terminal tips (tools/welcome/, put into every build context as rc-welcome/): what this image is and how
# to expose a web app with rc-tunnel. Printed once per home directory; `bash -c` and scripts stay silent.
COPY rc-welcome/ /tmp/rc-welcome/
RUN sh /tmp/rc-welcome/add_welcome.sh base "Base" && rm -rf /tmp/rc-welcome

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash
