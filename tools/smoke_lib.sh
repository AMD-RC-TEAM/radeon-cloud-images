# Shared smoke checks, appended to each image's smoke.sh by the smoke Job (see tools/release.py).
# jupyterlab_fast_path: the image must pass Radeon Cloud's launch-time JupyterLab check (otherwise every launch
# pip-installs JupyterLab), and the Jupyter layer must not have changed any package that was already installed.
jupyterlab_fast_path() {
  python_bin=$(command -v python || command -v python3)
  command -v jupyter >/dev/null 2>&1 || { echo "FAIL: no jupyter on PATH; launches would pip-install JupyterLab"; return 1; }
  "$python_bin" -c 'import importlib.metadata as m,sys;p=sys.version_info[:2];s=tuple(map(int,m.version("jupyter_server").split(".")[:2]));l=tuple(map(int,m.version("jupyterlab").split(".")[:2]));assert (3,10)<=p<=(3,12) and (2,14)<=s<(3,0) and (4,2)<=l<(5,0)' \
    || { echo "FAIL: JupyterLab missing or outside the platform's supported range"; return 1; }
  echo "jupyterlab: launch fast path OK"
  if [ -f /opt/pip-freeze-before.txt ]; then
    "$python_bin" - <<'PY'
import subprocess, sys
def freeze(lines):
    return {l.split("==")[0].lower(): l.strip() for l in lines if "==" in l}
before = freeze(open("/opt/pip-freeze-before.txt"))
now = freeze(subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True).stdout.splitlines())
changed = [f"{before[k]} -> {now.get(k)}" for k in before if now.get(k) != before[k]]
assert not changed, f"the Jupyter layer changed existing packages: {changed[:10]}"
print(f"jupyterlab: layer added {len(set(now) - set(before))} packages and changed none")
PY
  fi
}

# no_in_image_welcome: the first-shell help comes from the platform (D-20261114-06), not from the image.
no_in_image_welcome() {
  [ ! -e /etc/profile.d/rc-welcome.sh ] || { echo "FAIL: image still ships /etc/profile.d/rc-welcome.sh"; return 1; }
  ! grep -qs rc-welcome.sh /etc/bash.bashrc || { echo "FAIL: /etc/bash.bashrc still sources rc-welcome.sh"; return 1; }
  echo "welcome: none baked into the image (platform-mounted, D-20261114-06)"
}

# openssh_baked: sshd ships in the image, so Radeon Cloud's SSH setup skips its launch-time apt install
# (app/ssh_runtime.py checks `command -v sshd` / /usr/sbin/sshd first). No host keys may be baked in: the platform
# generates them per instance. The config test uses a throwaway host key, the way the platform starts sshd.
openssh_baked() {
  sshd_bin=$(command -v sshd 2>/dev/null || true); [ -n "$sshd_bin" ] || sshd_bin=/usr/sbin/sshd
  [ -x "$sshd_bin" ] || { echo "FAIL: no sshd in the image; SSH setup would apt-install openssh-server at launch"; return 1; }
  if ls /etc/ssh/ssh_host_*key >/dev/null 2>&1; then echo "FAIL: SSH host keys are baked into the image"; return 1; fi
  command -v ssh-keygen >/dev/null 2>&1 || { echo "FAIL: ssh-keygen missing (needed for per-instance host keys)"; return 1; }
  t=$(mktemp -d)
  ssh-keygen -q -t ed25519 -N '' -f "$t/hostkey" >/dev/null
  printf 'Port 2222\nHostKey %s/hostkey\nPidFile %s/sshd.pid\nUsePAM no\nPasswordAuthentication no\n' "$t" "$t" > "$t/sshd_config"
  mkdir -p /run/sshd 2>/dev/null || true
  "$sshd_bin" -t -f "$t/sshd_config" || { rm -rf "$t"; echo "FAIL: sshd rejects a minimal config"; return 1; }
  rm -rf "$t"
  echo "openssh: $(ssh -V 2>&1 | head -1 || true) present, no baked host keys; launch-time install is skipped"
}
