# upstream: docker.io/vllm/vllm-openai-rocm:v0.33.0-rocm72@sha256:4fe7bc121cbe2f0791ebc38dcc2f0d615612233b4bfc0c1f4b9daeab05aba182
# Built with Kaniko on top of the mirrored upstream image (same digest as upstream for the base layers).
FROM 10.5.10.12:1808/radeon-cloud-global/vllm/vllm-openai-rocm@sha256:4fe7bc121cbe2f0791ebc38dcc2f0d615612233b4bfc0c1f4b9daeab05aba182

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh
