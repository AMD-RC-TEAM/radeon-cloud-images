#!/bin/bash
set +e
export PATH=/opt/venv/bin:/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# --- 1) sshd: the IMAGE must start it (platform confirmed "sshd by image") ---
# The platform postStart hook only injects the pubkey + `service ssh reload`,
# which is a no-op when sshd is not already running. So we must start sshd here;
# the hook then reloads this running sshd to apply key-only auth. Using reload
# (not a second start) means there is no double-sshd conflict.
# Override: START_SSHD=no disables self-start.
if [ "${START_SSHD:-yes}" != "no" ]; then
  mkdir -p /run/sshd
  ssh-keygen -A 2>/dev/null
  if pgrep -x sshd >/dev/null 2>&1; then
    echo "[start] sshd already running"
  else
    /usr/sbin/sshd && echo "[start] sshd started by image" || echo "[start] WARN: sshd failed to start"
  fi
else
  echo "[start] sshd self-start disabled (START_SSHD=no)"
fi

# --- 2) ComfyUI: launched via container CMD (aligned with yygao) ---
exec "$@"
