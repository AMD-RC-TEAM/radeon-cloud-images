# upstream: docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e
# SGLang 0.5.23 (LLM serving) with its RDNA3 plugin, for Radeon PRO W7900 / W7900D (gfx1100).
# Follows the plugin's documented install (github.com/AMD-AIM/sglang-radeon, docs/installation.md): SGLang from its
# source tarball, its non-CUDA requirements, the plugin, and sgl-kernel built for gfx1100. The PyPI sglang wheel only
# declares CUDA dependencies and omits the kernel sources. hk-dsl is not included (paused, D-20261112-35).
# SGLang-Diffusion's extra packages are not included yet.
# The base is the same ROCm PyTorch image as "PyTorch · Stable"; torch, triton and ROCm come from it unchanged.
FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL
ARG SGLANG_VERSION=0.5.23

# Every package installed over the base is pinned in requirements.txt (pip's resolution of SGLang's non-CUDA
# requirements against this base, see its header) and installed with --no-deps.
COPY requirements.txt fetch_sglang_src.py /tmp/
RUN python3 /tmp/fetch_sglang_src.py ${SGLANG_VERSION} /opt/sglang-src \
 && pip install --no-cache-dir --no-deps -r /tmp/requirements.txt \
 && SETUPTOOLS_SCM_PRETEND_VERSION=${SGLANG_VERSION} SGLANG_BUILD_RUST_EXTS=none \
    pip install --no-cache-dir --no-deps --no-build-isolation /opt/sglang-src/python \
 && pip install --no-cache-dir /opt/rocm/share/amd_smi \
 && sglang-rdna3 build-kernel --sglang-src /opt/sglang-src --target gfx1100 --jobs 16 --install \
 && rm -rf /tmp/requirements.txt /tmp/fetch_sglang_src.py /root/.cache \
 && (pip check | grep -v -i -E "torch|triton|rocm|nvidia|cuda|flashinfer|sgl|tilelang|quack|deep|mistral" > /opt/pip-check.txt || true)

# SGLang imports aiter unconditionally on ROCm (quark MXFP4 schemes); the RDNA3 plugin stubs its CDNA-only kernels.
# aiter is installed for that import only; SGLANG_USE_AITER=0 keeps its kernels off.
ENV GPU_ARCHS=gfx1100 \
    SGLANG_USE_AITER=0 \
    MIOPEN_FIND_MODE=FAST \
    PYTORCH_ALLOC_CONF=expandable_segments:True

EXPOSE 30000
CMD ["bash"]
