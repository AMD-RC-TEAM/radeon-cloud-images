# <What this image is, for whom.> The public upstream image, pinned by digest; the pipeline mirrors it into Harbor.
FROM docker.io/<org>/<image>:<tag>@sha256:<digest>

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# Your build steps, if any (installed with pinned versions):
# RUN pip install --no-cache-dir '<package>==<version>'

# JupyterLab for the launch fast path (drop only if the upstream already ships a compatible one).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh
