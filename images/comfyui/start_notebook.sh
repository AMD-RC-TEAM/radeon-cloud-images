#!/bin/bash
set +e
export PATH=/opt/venv/bin:/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# --- 1) sshd (same as before) ---
if [ "${START_SSHD:-yes}" != "no" ]; then
  mkdir -p /run/sshd
  ssh-keygen -A 2>/dev/null
  if pgrep -x sshd >/dev/null 2>&1; then
    echo "[start] sshd already running"
  else
    /usr/sbin/sshd && echo "[start] sshd started by image" || echo "[start] WARN: sshd failed"
  fi
fi

# --- 2) Optional user-defined startup hook ---
for HOOK in /workspace/startup_hook.sh /comfyui_workspace/startup_hook.sh; do
  [ -f "$HOOK" ] && { echo "[start] running hook $HOOK"; bash "$HOOK"; break; }
done

# --- 3) Launch JupyterLab on port 8888 (no token, for platform proxy) ---
echo "[start] launching JupyterLab on 0.0.0.0:8888"
exec jupyter lab \
  --ip=0.0.0.0 \
  --port=8888 \
  --no-browser \
  --NotebookApp.token='' \
  --NotebookApp.password='' \
  --ServerApp.token='' \
  --ServerApp.password='' \
  --ServerApp.allow_origin='*' \
  --ServerApp.disable_check_xsrf=True \
  --notebook-dir=/root \
  --allow-root
