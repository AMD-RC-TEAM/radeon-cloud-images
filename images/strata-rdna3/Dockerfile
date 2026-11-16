# Strata for Radeon PRO W7900 / W7900D (gfx1100): one image, `strata-serve --model <name>`.
# DeepSeek engine is compiled here for gfx1100 only (no GPU at build). The runtime is the public
# upstream gfx110x image (Terminal + signed Qwen rx7900 engine). Weights are not in the image.
#
# The DeepSeek build FROM is docker.io (already used by SGLang). The runtime FROM is ghcr.io;
# Docker Hub is mirrored automatically, ghcr.io needs rc-ops to copy the digest first.
FROM docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e AS dsv41-build

ARG PIP_INDEX_URL
ARG STRATA_COMMIT=d2f096475817d4666c364c820b0ca830f751cfc5
ARG STRATA_SHA256=7093283d24ad4f9bc9a379607340678261c60e4539919c763c7555b1b5669195
ARG LLAMA_COMMIT=3cf03257f219afbe7334045ff7c6a06ac68c627d
ARG LLAMA_SHA256=c076d7534afa0e5d0ec2a0d425b11e791c16f3de0d727221aea071cef156a280

COPY fetch_src.py pr-5829.patch build_dsv41.sh check_manifest.py rc_strata.py models.yaml /tmp/rc/
RUN python3 /tmp/rc/fetch_src.py tar Niko1221/Strata ${STRATA_COMMIT} ${STRATA_SHA256} /src/strata \
 && python3 /tmp/rc/fetch_src.py tar ggml-org/llama.cpp ${LLAMA_COMMIT} ${LLAMA_SHA256} /src/llama.cpp \
 && patch -p1 -d /src/strata < /tmp/rc/pr-5829.patch \
 && python3 /tmp/rc/check_manifest.py /tmp/rc/models.yaml /src/strata/setup.py \
 && JOBS=16 sh /tmp/rc/build_dsv41.sh /src/strata /src/llama.cpp /out \
 && cp /src/strata/strata_control/dsv41_fit.py /out/dsv41_fit.py \
 && cp /opt/rocm/bin/rocminfo /out/rocminfo \
 && rm -rf /src /tmp/rc /root/.cache

# Public upstream runtime: Strata Terminal + signed Qwen rx7900 engine. No HIP compiler, no system Python.
FROM ghcr.io/niko1221/strata:0.2.13-rocm-gfx110x@sha256:a68f6ac1d013436115f025b6b6b95f30d9917a61d6ec418ff0517a49880d43e6

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

COPY --from=dsv41-build /out/components/dsv41/ /opt/strata/components/dsv41/
COPY --from=dsv41-build /out/dsv41_fit.py /out/rocminfo /tmp/rc-dsv41/
COPY models.yaml rc_strata.py strata-serve check_manifest.py README.md rc-strata-entry patch_entrypoint.py /tmp/rc/
RUN set -e \
 && exe=$(find /opt/strata/components/dsv41 -type f -name strata-dsv41 | head -n1) \
 && test -n "$exe" && test -x "$exe" \
 && printf '%s\n' "$exe" > /etc/strata-dsv41-exe \
 && install -d /opt/rc-strata \
 && install -m 644 /tmp/rc/models.yaml /tmp/rc/rc_strata.py /tmp/rc/README.md /opt/rc-strata/ \
 && install -m 755 /tmp/rc/strata-serve /tmp/rc/check_manifest.py /usr/local/bin/ \
 && install -m 755 /tmp/rc/rc-strata-entry /usr/local/bin/rc-strata-entry \
 && ln -sf /usr/local/bin/strata-serve /opt/rc-strata/strata-serve \
 && printf '0.2.13-m1\n' > /opt/rc-strata/VERSION \
 && /opt/strata/terminal/python/bin/python3 /tmp/rc/patch_entrypoint.py /opt/strata/entrypoint.sh \
 && fit=$(find /opt/strata/terminal -name dsv41_fit.py | head -n1) \
 && test -n "$fit" \
 && install -m 644 /tmp/rc-dsv41/dsv41_fit.py "$fit" \
 && install -m 755 /tmp/rc-dsv41/rocminfo "$(dirname "$exe")/rocminfo" \
 && printf '%s\n' '#!/bin/sh' "LD_LIBRARY_PATH=$(dirname "$exe"):\${LD_LIBRARY_PATH:-} exec $(dirname "$exe")/rocminfo \"\$@\"" > /usr/local/bin/rocminfo \
 && chmod 755 /usr/local/bin/rocminfo \
 && rm -rf /tmp/rc /tmp/rc-dsv41

# The upstream image has no system Python (only bundled CPython 3.12). JupyterLab needs its own.
# Ubuntu 24.04 is PEP 668; pip.conf lets add_jupyterlab.sh install without changing Strata's wheels.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip python3-venv ca-certificates curl procps libdrm2 \
 && printf '[global]\nbreak-system-packages = true\n' > /etc/pip.conf \
 && rm -rf /var/lib/apt/lists/*

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# First-terminal tips (tools/welcome/, put into every build context as rc-welcome/): what this image is and how
# to expose a web app with rc-tunnel. Printed once per home directory; `bash -c` and scripts stay silent.
COPY rc-welcome/ /tmp/rc-welcome/
RUN sh /tmp/rc-welcome/add_welcome.sh "Strata on RDNA3 (gfx1100): strata-serve --model <name>" "/opt/rc-strata/README.md" "Strata API: strata-serve --model <name> then rc-tunnel expose --port 8080" && rm -rf /tmp/rc-welcome

ENV STRATA_FEED_MODELS=0 \
    STRATA_MODELS_YAML=/opt/rc-strata/models.yaml \
    STRATA_MODELS_ROOT=/data/models \
    STRATA_DATA_DIR=/data/Strata-data \
    PORT=8080 \
    SHELL=/bin/bash \
    HSA_USERPTR_FOR_PAGED_MEM=0

EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/rc-strata-entry"]
