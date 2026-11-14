# SGLang (LLM serving) with the RDNA3 plugin, for Radeon PRO W7900 / W7900D (gfx1100), following the plugin's
# documented install (github.com/AMD-AIM/sglang-radeon, docs/installation.md): SGLang from source, its non-CUDA
# requirements, the plugin, and sgl-kernel built for gfx1100. hk-dsl is not included (paused, D-20261112-35).
#
# Why this SGLang commit: SGLang on ROCm needs sgl-kernel compiled for gfx1100, which the plugin's build-kernel
# does by patching SGLang's kernel sources. The newest plugin release (sglang-radeon-rdna3 0.2.0) is validated on
# SGLang 51b27f7 (main, 2026-08-24, between v0.5.18 and v0.5.19); against newer SGLang (0.5.23) its patches no
# longer apply and it refuses to build. This is the newest SGLang that works on gfx1100 today. Upgrade when a plugin
# release supports newer SGLang: the upgrade bot watches the plugin on PyPI (image.yaml watch_pypi).
# SGLang-Diffusion: its extra packages are pinned in requirements-diffusion.txt (see its header for what differs from
# SGLang's [diffusion] extra and what is left out as CUDA-only).
FROM docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL
ARG SGLANG_COMMIT=51b27f747ade4a267f37a29457bc8c690100ca9e
# setuptools-scm cannot see git history in a tarball; this is the version it would compute for that commit.
ARG SGLANG_VERSION=0.5.19.dev338+g51b27f7

# Every package installed over the base is pinned in requirements.txt (see its header), installed with --no-deps.
COPY requirements.txt requirements-diffusion.txt fetch_sglang_src.py /tmp/
RUN python3 /tmp/fetch_sglang_src.py ${SGLANG_COMMIT} /opt/sglang-src \
 && pip install --no-cache-dir --no-deps -r /tmp/requirements.txt \
 && pip install --no-cache-dir --no-deps -r /tmp/requirements-diffusion.txt \
 && SETUPTOOLS_SCM_PRETEND_VERSION=${SGLANG_VERSION} SGLANG_BUILD_RUST_EXTS=none \
    pip install --no-cache-dir --no-deps --no-build-isolation /opt/sglang-src/python \
 && pip install --no-cache-dir /opt/rocm/share/amd_smi \
 && sglang-rdna3 build-kernel --sglang-src /opt/sglang-src --target gfx1100 --jobs 16 --install \
 && rm -rf /tmp/requirements.txt /tmp/requirements-diffusion.txt /tmp/fetch_sglang_src.py /root/.cache \
 && (pip check | grep -v -i -E "torch|triton|rocm|nvidia|cuda|flashinfer|sgl|tilelang|quack|deep|mistral|tokenspeed" > /opt/pip-check.txt || true)

# RDNA3 serving defaults (triton attention, no CUDA graphs), so a plain `python -m sglang.launch_server` works.
COPY rc_sglang_defaults.py rc_sglang_defaults.pth README.md /tmp/rc/
RUN SP=$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])") \
 && install -m 644 /tmp/rc/rc_sglang_defaults.py /tmp/rc/rc_sglang_defaults.pth "$SP"/ \
 && install -D -m 644 /tmp/rc/README.md /opt/sglang/README.md \
 && rm -rf /tmp/rc

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# SGLang imports aiter unconditionally on ROCm (quark MXFP4 schemes); the plugin stubs its CDNA-only kernels.
# aiter is installed for that import only: its kernels stay off (SGLANG_USE_AITER=0, no aiter RoPE).
ENV GPU_ARCHS=gfx1100 \
    SGLANG_USE_AITER=0 \
    USE_ROCM_AITER_ROPE_BACKEND=0 \
    MIOPEN_FIND_MODE=FAST \
    PYTORCH_ALLOC_CONF=expandable_segments:True

EXPOSE 30000
CMD ["bash"]

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash
