# RoboTwin LingBot-VLA-v2 ROCm runtime for inference, evaluation, and training with data on the read-only model mount.
FROM docker.io/rocm/pytorch:rocm7.2.1_ubuntu24.04_py3.12_pytorch_release_2.9.1@sha256:96a2fb24dec9896e2f8238178f0c49d0dcc4c7dcc597be09e4564316bd86d191

LABEL org.opencontainers.image.title="RoboTwin LingBot-VLA-v2 ROCm external-data runtime" \
      org.opencontainers.image.description="ROCm runtime using an external mount for RoboTwin assets, datasets, and models"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    HF_HOME=/workspace/runtime/.cache/huggingface \
    TMPDIR=/tmp \
    HF_LEROBOT_HOME=/RoboTwin/data/lerobot \
    LEROBOT_VIDEO_BACKEND=pyav \
    LEROBOT_VIDEO_CODEC=h264 \
    PYOPENGL_PLATFORM=egl \
    ROBOTWIN_DISABLE_CUROBO=1 \
    ROBOTWIN_EE_PLANNER=mplib \
    TOKENIZERS_PARALLELISM=false \
    AITER_TRITON_ONLY=1 \
    FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE \
    ROBOTWIN_ROOT=/RoboTwin \
    LINGBOT_VLA_SOURCE=/RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/source/lingbot-vla-v2 \
    QWEN3VL_PATH=/RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models/Qwen3-VL-4B-Instruct-config-tokenizer \
    LINGBOT_VLA_PYTHON=/opt/robotwin-env/bin/python \
    PYTHONPATH=/opt/aiter

ARG PIP_INDEX_URL=
ARG ROBOTWIN_COMMIT=e154702de28cac4b9bfe0299044303f507236bb3
ARG XPOLICYLAB_COMMIT=c37109c500be67d0dea6b36bf7337bbd26e763cd
ARG LINGBOT_VLA_COMMIT=951475ae1b1d87553e7dc47c97b53a3d695c0d13
ARG AITER_COMMIT=9bab8388c35936814a659b4ebd245c491e1b940a
ARG FLASH_ATTENTION_COMMIT=9c6d9297e5d43653c2ea5837ed9e0d10f76ed231
ARG AITER_GPU_ARCHS=gfx1100;gfx1201

RUN mkdir -p /workspace/runtime/tmp /workspace/runtime/.cache/huggingface

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        ca-certificates git git-lfs curl wget ffmpeg \
        libgl1 libglib2.0-0 libvulkan1 vulkan-tools mesa-vulkan-drivers \
        build-essential ninja-build cmake pkg-config \
        openssh-server vim unzip && \
    git lfs install --system && \
    rm -f /etc/ssh/ssh_host_*

COPY requirements.txt /tmp/robotwin-requirements.txt

RUN /opt/venv/bin/python -m venv --system-site-packages /opt/robotwin-env && \
    MODEL_SITE="$(/opt/robotwin-env/bin/python -c 'import site; print(site.getsitepackages()[0])')" && \
    BASE_SITE="$(/opt/venv/bin/python -c 'import site; print(site.getsitepackages()[0])')" && \
    printf '%s\n' "${BASE_SITE}" > "${MODEL_SITE}/rocm_image_venv.pth" && \
    awk '/^(pip|setuptools|wheel)==/{print}' /tmp/robotwin-requirements.txt > /tmp/robotwin-build-tools.txt && \
    /opt/robotwin-env/bin/python -m pip install --no-deps -r /tmp/robotwin-build-tools.txt && \
    /opt/robotwin-env/bin/python -m pip install --no-deps --no-build-isolation --prefer-binary \
        -r /tmp/robotwin-requirements.txt

RUN /opt/robotwin-env/bin/python -c 'import torch, torchvision, numpy, sapien, mplib, lerobot, jupyterlab, tornado, pipeline, utils3d; \
assert torch.__file__.startswith("/opt/venv/") and torch.version.hip; \
assert numpy.__version__ == "1.26.4" and sapien.__version__ == "3.0.0b1" and lerobot.__version__ == "0.6.0"'

COPY fetch_src.py /tmp/fetch_src.py
COPY robotwin-env.sh /usr/local/bin/robotwin-env
RUN chmod 0755 /usr/local/bin/robotwin-env && \
    ln -sf /usr/local/bin/robotwin-env /etc/profile.d/robotwin-env.sh

RUN git init /opt/aiter && \
    git -C /opt/aiter remote add origin https://github.com/ROCm/aiter.git && \
    git -C /opt/aiter fetch --depth 1 origin "${AITER_COMMIT}" && \
    git -C /opt/aiter checkout FETCH_HEAD && \
    cd /opt/aiter && \
    sed -i '/flydsl==0.1.9.dev599/d' pyproject.toml && \
    GPU_ARCHS="${AITER_GPU_ARCHS}" AITER_USE_SYSTEM_TRITON=1 \
        /opt/robotwin-env/bin/python setup.py develop && \
    python3 /tmp/fetch_src.py Dao-AILab/flash-attention "${FLASH_ATTENTION_COMMIT}" /tmp/flash-attention && \
    cd /tmp/flash-attention && \
    AITER_TRITON_ONLY=1 \
    GPU_ARCHS="${AITER_GPU_ARCHS}" \
    FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE \
    FLASH_ATTENTION_USE_SYSTEM_AITER=TRUE \
        /opt/robotwin-env/bin/python -m pip install \
        --no-build-isolation --no-deps . && \
    cd / && rm -rf /tmp/flash-attention

RUN /opt/robotwin-env/bin/python -c 'from importlib.metadata import version; import aiter, flash_attn, triton; \
assert version("flash-attn") == "2.8.4"; print("AITER", version("amd-aiter"), "Triton", triton.__version__)'

COPY lingbot-vla-v2-rocm.patch robotwin-rocm-reproduction.patch xpolicylab-lerobot-v30.patch /tmp/robotwin-patches/
RUN python3 /tmp/fetch_src.py RoboTwin-Platform/RoboTwin "${ROBOTWIN_COMMIT}" /RoboTwin && \
    python3 /tmp/fetch_src.py XPolicyLab/XPolicyLab "${XPOLICYLAB_COMMIT}" /RoboTwin/XPolicyLab && \
    git -C /RoboTwin apply --check /tmp/robotwin-patches/robotwin-rocm-reproduction.patch && \
    git -C /RoboTwin apply /tmp/robotwin-patches/robotwin-rocm-reproduction.patch && \
    git -C /RoboTwin/XPolicyLab apply --check /tmp/robotwin-patches/xpolicylab-lerobot-v30.patch && \
    git -C /RoboTwin/XPolicyLab apply /tmp/robotwin-patches/xpolicylab-lerobot-v30.patch && \
    python3 /tmp/fetch_src.py robbyant/lingbot-vla-v2 "${LINGBOT_VLA_COMMIT}" \
        /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/source/lingbot-vla-v2 && \
    git -C /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/source/lingbot-vla-v2 \
        apply --check /tmp/robotwin-patches/lingbot-vla-v2-rocm.patch && \
    git -C /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/source/lingbot-vla-v2 \
        apply /tmp/robotwin-patches/lingbot-vla-v2-rocm.patch && \
    /opt/robotwin-env/bin/python -m pip install --no-deps --no-build-isolation \
        -e /RoboTwin/XPolicyLab \
        -e /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/source/lingbot-vla-v2 && \
    rm -rf /tmp/robotwin-patches /tmp/fetch_src.py

RUN /opt/robotwin-env/bin/python -m py_compile /RoboTwin/scripts/eval_policy_xpolicylab.py && \
    test -f /RoboTwin/XPolicyLab/XPolicyLab.py

RUN rm -rf \
        /RoboTwin/assets \
        /RoboTwin/data \
        /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models && \
    mkdir -p \
        /models/robotwin-persistent \
        /workspace/runtime \
        /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/training && \
    ln -s /models/robotwin-persistent/assets /RoboTwin/assets && \
    ln -s /models/robotwin-persistent/data /RoboTwin/data && \
    ln -s /models/robotwin-persistent/models \
        /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models && \
    ln -s /workspace/runtime/eval_result /RoboTwin/eval_result && \
    ln -s /workspace/RoboTwin-radeon-cloud/scripts \
        /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/scripts && \
    ln -s /workspace/RoboTwin-radeon-cloud/configs/lingbot_vla_v2_6b_robotwin/lingbotvla_cli.yaml \
        /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/training/lingbotvla_cli.yaml

WORKDIR /RoboTwin
ENV VIRTUAL_ENV=/opt/robotwin-env \
    PATH=/opt/robotwin-env/bin:${PATH} \
    SHELL=/bin/bash
RUN command -v jupyter && python -c 'import importlib.metadata as m,sys; \
v=lambda n: tuple(map(int,m.version(n).split(".")[:2])); \
assert (3,10)<=sys.version_info[:2]<=(3,12) and (2,14)<=v("jupyter_server")<(3,0) and (4,2)<=v("jupyterlab")<(5,0); \
import torch,jupyterlab,lingbotvla; assert torch.__file__.startswith("/opt/venv/")'
