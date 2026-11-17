# EXAMPLE ONLY: a worked example of a new image for other developers to copy. This PR is a draft and is never merged
# (merging to main releases the image).
#
# Line 1 of every image: what the image is and who it is for, in one English sentence.
# A tiny PyTorch image that shows the parts every Radeon Cloud image needs.
#
# FROM: the PUBLIC upstream image, pinned by tag AND digest.
# - Never write our Harbor address here; `validate` rejects it. The pipeline mirrors this digest into Harbor
#   (tools/mirror.sh) and builds and smokes from the Harbor copy, so cluster nodes never pull from the internet.
# - Docker Hub upstreams are mirrored automatically; ask rc-ops before using any other registry.
# - This example reuses the PyTorch · Stable upstream, which is already mirrored, so its PR check is fast.
# - Get a digest with: docker buildx imagetools inspect docker.io/<org>/<image>:<tag>
FROM docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1

# The build passes a PyPI mirror that the build cluster can reach. Declare the ARG before any pip install; it is
# not kept in the image.
ARG PIP_INDEX_URL

# Your own build steps, every version pinned (example: one small pure-Python package):
RUN python3 -m pip install --no-cache-dir 'rich==13.9.4'

# JupyterLab for the launch fast path. The platform checks for jupyter_server 2.14–2.x and jupyterlab 4.2–4.x on
# Python 3.10–3.12, and installs them on every launch if they're missing (18–188 s). add_jupyterlab.sh adds a
# pinned JupyterLab without changing anything already installed; the smoke verifies that.
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# JupyterLab terminals run "$SHELL -l" and fall back to sh (no history, no completion) when SHELL is unset.
ENV SHELL=/bin/bash

# Do NOT do any of these:
# - No ENTRYPOINT/CMD that dispatches on arguments (e.g. "no args = Jupyter, args = my server"). The platform
#   starts instances with its own command; ship your tools on PATH instead (docker run <image> mytool ...).
# - No welcome/help text baked into the image. The platform mounts the first-shell help into every instance
#   (D-20261114-06).
# - No model weights or datasets in the image. Download at runtime into the user's volume (HF_ENDPOINT is set
#   on the platform), and document the sizes in README.md.
# - English only: comments, README, script output.
