# ComfyUI for Radeon PRO W7900 / W7900D (gfx1100). A compatibility rebuild of the earlier ComfyUI image (ComfyUI 0.25.0
# on ROCm 7.2.4 / Ubuntu 22.04) on a current stack: ComfyUI v0.45.0 on the same ROCm PyTorch base as PyTorch · Stable.
# Everything users rely on stays where it was: /comfyui_workspace/ComfyUI, /comfyui_user, /opt/venv, /start.sh,
# /start_notebook.sh (the entrypoint: JupyterLab on 8888), /usr/local/bin/start_comfyui_no_default_workflow.sh (ComfyUI
# on $COMFY_PORT, 8188), /usr/local/bin/start_cloudflare_tunnel.sh with cloudflared, the ComfyUI-CacheDiT node, sshd.
FROM docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL
ARG COMFYUI_COMMIT=989d93d0d968e704c589ce0146bb18c77f6b50cc
ARG CACHEDIT_COMMIT=ab1a1448a2476a33493c9a9b04e1685971b9e73a
ARG CLOUDFLARED_VERSION=2026.6.1
ARG CLOUDFLARED_SHA256=5861a10a438fe8ddcfebb3b830f83966cbf193edafce0fe2eeb198fbae1f7a22

ENV DEFAULT_WORKFLOW= \
    COMFY_PORT=8188 \
    DEBIAN_FRONTEND=noninteractive \
    LD_LIBRARY_PATH=/opt/rocm/lib \
    PATH=/opt/venv/bin:/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# sshd (started by /start.sh and /start_notebook.sh, as before) and git for custom-node installs. The Ubuntu mirror is
# the one the build cluster can reach; the original sources are restored afterwards.
RUN cp /etc/apt/sources.list.d/ubuntu.sources /tmp/ubuntu.sources \
 && sed -i -e 's#http://archive.ubuntu.com#http://mirrors.aliyun.com#g' -e 's#http://security.ubuntu.com#http://mirrors.aliyun.com#g' \
        /etc/apt/sources.list.d/ubuntu.sources \
 && apt-get update && apt-get install -y --no-install-recommends openssh-server git ca-certificates curl \
 && mv /tmp/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd

COPY requirements.txt fetch_src.py README.md /tmp/rc/
RUN python3 /tmp/rc/fetch_src.py tar comfyanonymous/ComfyUI ${COMFYUI_COMMIT} /comfyui_workspace/ComfyUI \
 && python3 /tmp/rc/fetch_src.py tar Jasonzzt/ComfyUI-CacheDiT ${CACHEDIT_COMMIT} \
        /comfyui_workspace/ComfyUI/custom_nodes/ComfyUI-CacheDiT \
 && python3 /tmp/rc/fetch_src.py file \
        https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-amd64 \
        ${CLOUDFLARED_SHA256} /usr/local/bin/cloudflared \
 && chmod 755 /usr/local/bin/cloudflared \
 && pip install --no-cache-dir --no-deps -r /tmp/rc/requirements.txt \
 && mkdir -p /comfyui_user/default /workspace && install -D -m 644 /tmp/rc/README.md /opt/comfyui/README.md \
 && rm -rf /tmp/rc /root/.cache

COPY start.sh start_notebook.sh /
COPY start_comfyui_no_default_workflow.sh start_cloudflare_tunnel.sh /usr/local/bin/
RUN chmod 755 /start.sh /start_notebook.sh /usr/local/bin/start_comfyui_no_default_workflow.sh \
        /usr/local/bin/start_cloudflare_tunnel.sh

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

WORKDIR /root
EXPOSE 22 8888
ENTRYPOINT ["/start_notebook.sh"]
