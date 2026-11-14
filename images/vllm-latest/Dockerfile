# The public upstream image, pinned by digest; the pipeline mirrors it into Harbor and builds/smokes from there.
FROM docker.io/vllm/vllm-openai-rocm:v0.33.0-rocm100@sha256:4fcd39b758b660c4e9c345c021e2ea8f0ccdb31e3c32507d676cc3005ae83fba

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

# First-terminal tips (tools/welcome/, put into every build context as rc-welcome/): what this image is and how
# to expose a web app with rc-tunnel. Printed once per home directory; `bash -c` and scripts stay silent.
COPY rc-welcome/ /tmp/rc-welcome/
RUN sh /tmp/rc-welcome/add_welcome.sh "Official vLLM for ROCm, newest release channel: OpenAI-compatible model serving" "/opt/vllm/README.md" "Faster serving on Radeon: pip install hk-dsl, then vllm serve as usual (HK_DISABLE=1 turns it off)." && rm -rf /tmp/rc-welcome
