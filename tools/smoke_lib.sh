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
