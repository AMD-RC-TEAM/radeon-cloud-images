# upstream: docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e
# SGLang 0.5.23 (LLM serving and SGLang-Diffusion) with its RDNA3 plugin, for Radeon PRO W7900 / W7900D (gfx1100).
# Based on the SGLang image prepared by hk-dsl lane B, without hk-dsl (paused, D-20261112-35).
# The base is the same ROCm PyTorch image as "PyTorch · Stable"; torch, triton and ROCm come from it unchanged.
FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# Every package installed over the base is pinned in requirements.txt and installed with --no-deps, so the base
# image's ROCm PyTorch and Triton stay as they are.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --no-deps -r /tmp/requirements.txt \
 && rm -f /tmp/requirements.txt \
 && pip install --no-cache-dir /opt/rocm/share/amd_smi \
 && (pip check | grep -v -i -E "torch|triton|rocm" > /opt/pip-check.txt || true)

ENV SGLANG_USE_AITER=0 \
    MIOPEN_FIND_MODE=FAST \
    PYTORCH_ALLOC_CONF=expandable_segments:True

EXPOSE 30000
CMD ["bash"]
