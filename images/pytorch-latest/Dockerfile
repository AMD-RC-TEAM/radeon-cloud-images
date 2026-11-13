# upstream: docker.io/rocm/pytorch:rocm10.1.0_ubuntu24.04_py3.12_pytorch_release_2.14.0@sha256:099f59a3bee9c436f5cc57db6bc6076fdeda579c57e9e22ae40f856d5905b3e4
# Built with Kaniko on top of the mirrored upstream image (same digest as upstream for the base layers).
FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch@sha256:099f59a3bee9c436f5cc57db6bc6076fdeda579c57e9e22ae40f856d5905b3e4

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh
