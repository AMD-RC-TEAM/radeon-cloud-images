# The public upstream image, pinned by digest; the pipeline mirrors it into Harbor and builds/smokes from there.
FROM docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1

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

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash

# Use rocBLAS, not hipBLASLt, for torch matmuls on the W7900D (gfx1100): fp32 GEMM is ~8x faster (22 vs 2.6 TFLOPS at
# 4096^3) and bf16 ~20% faster; fp32 training was ~3x slower without it. smoke_lib.sh torch_gemm_floor checks it.
# Remove when hipBLASLt matches rocBLAS on gfx1100 at all sizes (re-measure with torch_gemm_floor and bigger shapes).
ENV TORCH_BLAS_PREFER_HIPBLASLT=0

# Size CPU thread pools to the instance's CPU limit, not the host's 128 cores (numpy ~2.5x faster on a 16-CPU instance);
# a user's own OMP/OPENBLAS/MKL_NUM_THREADS always wins. See add_cpu_threads.sh; smoke: cpu_threads_match_limit.
COPY add_cpu_threads.sh /tmp/add_cpu_threads.sh
RUN sh /tmp/add_cpu_threads.sh && rm -f /tmp/add_cpu_threads.sh
