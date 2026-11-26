# Strata (our RDNA3 inference engine) serving Qwen3.8-Flash-Next (IQ3_XXS) on one W7900D, OpenAI-compatible API.
# 1-GPU instances only for now (owner decision D-20261125-10: single card first, RC template first).
# The base is the public ROCm 7.2.1 dev image: the engine is built and measured against ROCm 7.2.1 libraries (no torch needed).
FROM docker.io/rocm/dev-ubuntu-24.04:7.2.1-complete@sha256:3db551c4e1229aac1857ac44fcb6141bb749f41348eb572452f11279153c13c3

ARG APT_MIRROR=mirrors.aliyun.com
ARG PIP_INDEX_URL

# Python for JupyterLab and the platform's launch check: a venv at /opt/venv, first on PATH (as in the other images).
RUN sed -i -e "s@//[a-z.]*archive.ubuntu.com@//${APT_MIRROR}@g" -e "s@//security.ubuntu.com@//${APT_MIRROR}@g" \
        /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null || true; \
    DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-venv python3-pip curl && \
    rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:${PATH}

COPY add_openssh.sh /tmp/add_openssh.sh
RUN sh /tmp/add_openssh.sh && rm -f /tmp/add_openssh.sh
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh && \
    pip install --no-cache-dir 'jupyter-server-proxy==4.4.0' && pip check

# The engine bundle (scripts + engine binaries, 13 MB) comes from a small sha-pinned image in our Harbor, not from git.
# It was copied there from radeon-engine4's artifact server after checking its SHA256SUMS; the sha is checked again here.
# COPY --from cannot take a build variable, so the reference is written out and pinned by digest (repo README:
# "Build inputs from Harbor"). To update: push the new bundle the same way, change these three lines, re-measure.
ARG STRATA_BUNDLE_VERSION=v3.1
ARG STRATA_BUNDLE_SHA256=03bfd8a1ee3d7aa92df8f97d0c02d4fffc3c34ee43dddef9995d767b181e3563
COPY --from=10.5.10.12:1808/radeon-cloud-global/rc-artifacts/strata-bundle@sha256:a6f1be5a972dd27c0f1d790531147d4ca9ce96ea8f87a1c56a41b560f651cc74 /bundle/context.tgz /tmp/strata/context.tgz
COPY add_strata.sh /tmp/add_strata.sh
RUN sh /tmp/add_strata.sh && rm -f /tmp/add_strata.sh

# Start the server next to JupyterLab (the platform runs `jupyter lab`, so no CMD), and reach it via jupyter-server-proxy.
# No notebooks or files for /workspace in the image: the template clones its notebook repo there (as for the workshops).
COPY rc_strata_autostart.py /opt/venv/lib/python3.12/site-packages/rc_strata_autostart.py
COPY rc_strata.json /opt/venv/etc/jupyter/jupyter_server_config.d/rc_strata.json

# Server settings. It listens on 127.0.0.1 only: inside the instance and through the Jupyter proxy, never directly.
# No per-instance API key: the gateway replaces the Authorization header with the Jupyter token, so access control is
# the gateway's per-instance login (design decision, approved 11-25). STRATA_ALLOWED_HOSTS="*": without a key the server
# answers only listed Host headers (a DNS-rebinding guard), and jupyter-server-proxy may forward the instance's public
# Host, which would turn every proxied call into a 403. Safe here because the server listens on 127.0.0.1 only.
ENV B0_MODEL=/models/qwen38-flash-next-iq3xxs B0_APP=/opt/strata/control B0_PY=/opt/strata/venv/bin/python \
    B0_HOST=127.0.0.1 B0_PORT=8080 B0_LOG=/tmp/b0-logs STRATA_ALLOWED_HOSTS="*" \
    HSA_DISABLE_COREDUMP_ON_EXCEPTION=1 SHELL=/bin/bash

# Keep the image toolchain environment in SSH sessions; see keep_image_env.sh. Last step: after every ENV.
COPY keep_image_env.sh /tmp/keep_image_env.sh
RUN sh /tmp/keep_image_env.sh && rm -f /tmp/keep_image_env.sh
