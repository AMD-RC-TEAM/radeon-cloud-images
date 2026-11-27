# Dream Circuit Lap course (https://github.com/wangxunx/dream-circuit-lap) on Radeon PRO W7900 / W7900D (gfx1100):
# ComfyUI v0.45.0 on the PyTorch · Stable base with the course's two cloud nodes, the Qwen Image 2.1 models for its local
# car edit, and a copy of its media and fonts. The course itself (notebooks/cloud.ipynb) is not baked in: the Radeon
# Cloud template clones it into /workspace, so course updates need no image rebuild.
FROM docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL
ARG COMFYUI_COMMIT=989d93d0d968e704c589ce0146bb18c77f6b50cc
# The course notebook and scripts/start_comfyui_cloud.sh look for ComfyUI here.
ENV COMFY_DIR=/opt/ComfyUI

COPY requirements.txt fetch.py models.txt README.md /tmp/rc/
RUN python3 /tmp/rc/fetch.py src comfyanonymous/ComfyUI ${COMFYUI_COMMIT} /opt/ComfyUI \
 && pip install --no-cache-dir --no-deps -r /tmp/rc/requirements.txt \
 && install -D -m 644 /tmp/rc/README.md /opt/dream-circuit-lap/README.md \
 && rm -rf /root/.cache

# The local car edit of chapters 4 and 7 (about 17 GB, models.txt): Hugging Face through hf-mirror.com first
# (huggingface.co is not reachable from the build cluster), then huggingface.co itself; checked by sha256 either way.
ARG QWEN_IMAGE_REVISION=aacf31a6d48e707f352ecba714cee0680da3479b
RUN grep -v '^#' /tmp/rc/models.txt | while read -r sha path; do \
      u="Comfy-Org/Qwen-Image-2.1/resolve/${QWEN_IMAGE_REVISION}/${path}"; \
      python3 /tmp/rc/fetch.py file "$sha" "/opt/ComfyUI/models/$path" "https://hf-mirror.com/$u" "https://huggingface.co/$u" || exit 1; \
    done

# The course's historical clips (media/manifest.json, about 72 MB) and Noto Sans SC. The course's fetch_media.py copies
# them from DREAM_CIRCUIT_MEDIA_CACHE when they match its manifest, and falls back to them when a download fails.
# GitHub release assets time out from the build cluster, so they go through GITHUB_PROXY first (empty: github.com only).
ARG COURSE_COMMIT=1bfaff212a3243328bca2522d0e2f13ebb40817a
ARG GITHUB_PROXY=https://gh-proxy.com/
RUN python3 /tmp/rc/fetch.py src wangxunx/dream-circuit-lap ${COURSE_COMMIT} /tmp/rc/course \
 && python3 -c 'import json; m = json.load(open("/tmp/rc/course/media/manifest.json")); \
[print(f["sha256"], "media/" + n, m["base_url"] + "/" + n) for n, f in m["files"].items()]; \
[print(f["sha256"], "fonts/" + n, f["url"]) for n, f in m["fonts"].items()]' > /tmp/rc/media.txt \
 && while read -r sha path url; do \
      python3 /tmp/rc/fetch.py file "$sha" "/opt/dream-circuit-lap/$path" ${GITHUB_PROXY:+"${GITHUB_PROXY}${url}"} "$url" || exit 1; \
    done < /tmp/rc/media.txt \
 && cp /tmp/rc/course/media/manifest.json /opt/dream-circuit-lap/manifest.json \
 && rm -rf /tmp/rc/course /tmp/rc/media.txt

# The two cloud nodes (keyframes and videos through the H3 gateway), so the notebook's install cell skips cloning them.
ARG QWEN_NODE_COMMIT=25043038b6f5bfd66ea39e11dc7e6cc9b600ee19
ARG H3_NODE_COMMIT=37a6fa90a239f81717ef700e875d8fc92a502c85
RUN python3 /tmp/rc/fetch.py src wangxunx/ComfyUI-AMD-Qwen-Image-2.1 ${QWEN_NODE_COMMIT} /opt/ComfyUI/custom_nodes/ComfyUI-AMD-Qwen-Image-2.1 \
 && python3 /tmp/rc/fetch.py src wangxunx/ComfyUI-AMD-MiniMaxH3 ${H3_NODE_COMMIT} /opt/ComfyUI/custom_nodes/ComfyUI-AMD-MiniMaxH3 \
 && rm -rf /tmp/rc

ENV DREAM_CIRCUIT_MEDIA_CACHE=/opt/dream-circuit-lap/media \
    F1_FONT_REGULAR=/opt/dream-circuit-lap/fonts/NotoSansSC-Regular.otf \
    F1_FONT_BOLD=/opt/dream-circuit-lap/fonts/NotoSansSC-Bold.otf

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

# Use rocBLAS, not hipBLASLt, for torch matmuls on the W7900D (gfx1100); see images/comfyui/Dockerfile.
# smoke_lib.sh torch_gemm_floor checks it.
ENV TORCH_BLAS_PREFER_HIPBLASLT=0
