#!/bin/bash
set -e

export PATH=/opt/venv/bin:/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export COMFY_PORT=${COMFY_PORT:-8188}

# Ensure this image never forces a default workflow to open.
unset DEFAULT_WORKFLOW

cd /comfyui_workspace/ComfyUI
exec python3 main.py --listen 0.0.0.0 --port "${COMFY_PORT}" "$@"
