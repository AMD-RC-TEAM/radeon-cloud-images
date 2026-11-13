# The public upstream image, pinned by digest; the pipeline mirrors it into Harbor and builds/smokes from there.
FROM docker.io/vllm/vllm-openai-rocm:v0.33.0-rocm72@sha256:4fe7bc121cbe2f0791ebc38dcc2f0d615612233b4bfc0c1f4b9daeab05aba182

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL

# RDNA3 serving default: ROCM_SEGMENTED_ATTN attention on gfx11 when no --attention-backend is given
# (rc_vllm_defaults.py; about 2x faster long-context prefill than TRITON_ATTN on W7900D). The README goes to /opt/vllm.
COPY rc_vllm_defaults.py rc_vllm_defaults.pth README.md /tmp/rc/
RUN SP=$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])") \
 && install -m 644 /tmp/rc/rc_vllm_defaults.py /tmp/rc/rc_vllm_defaults.pth "$SP"/ \
 && install -D -m 644 /tmp/rc/README.md /opt/vllm/README.md \
 && rm -rf /tmp/rc

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh
