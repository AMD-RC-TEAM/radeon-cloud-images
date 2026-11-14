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

# welcome_once: the first-shell tips print once in an interactive shell, never in `bash -c`, and not again.
# Only our block (from "Radeon Cloud:" to "Hide this message") is checked; the image's own bashrc may print other lines.
welcome_block() { sed -n '/^Radeon Cloud:/,/^Hide this message/p'; }
welcome_once() {
  local h first; h=$(mktemp -d)
  [ -z "$(HOME=$h bash -c 'true' 2>&1 | welcome_block)" ] || { echo "FAIL: welcome printed in a non-interactive shell"; return 1; }
  first=$(HOME=$h bash -i -c 'true' 2>/dev/null | welcome_block)
  [ -n "$first" ] || { echo "FAIL: no welcome in the first interactive shell"; return 1; }
  [ "$(printf '%s\n' "$first" | wc -l)" -le 8 ] || { echo "FAIL: welcome is longer than 8 lines"; return 1; }
  [ -z "$(HOME=$h bash -i -c 'true' 2>/dev/null | welcome_block)" ] || { echo "FAIL: welcome printed twice"; return 1; }
  echo "welcome: once in an interactive shell, silent otherwise"; printf '%s\n' "$first" | sed 's/^/  | /'
}

# welcome_jupyter_terminal: the tips also appear in a JupyterLab terminal. jupyter_server starts terminals as
# "$SHELL -l" (or "sh -l" when SHELL is unset): a login shell, which reads /etc/profile.d/ (and, for bash, the
# user's ~/.profile -> ~/.bashrc -> /etc/bash.bashrc path too). This opens a real terminal over the REST and websocket
# API in a fresh home directory and checks the block is printed.
welcome_jupyter_terminal() {
  python3 - <<'PY'
import asyncio, json, os, subprocess, tempfile, time, urllib.request
from tornado.websocket import websocket_connect
home, port, tok = tempfile.mkdtemp(), 18899, "rcsmoke"
env = dict(os.environ, HOME=home)
p = subprocess.Popen(["jupyter", "server", "--no-browser", f"--port={port}", f"--ServerApp.token={tok}", "--allow-root",
                      f"--ServerApp.root_dir={home}"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
base = f"http://127.0.0.1:{port}"
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/api/status?token={tok}", timeout=2); break
        except Exception:
            time.sleep(1)
    req = urllib.request.Request(f"{base}/api/terminals?token={tok}", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    name = json.load(urllib.request.urlopen(req, timeout=10))["name"]

    async def read():
        ws = await websocket_connect(f"ws://127.0.0.1:{port}/terminals/websocket/{name}?token={tok}")
        out, t0 = "", time.time()
        while time.time() - t0 < 10 and "Hide this message" not in out:
            try:
                m = await asyncio.wait_for(ws.read_message(), timeout=2)
            except asyncio.TimeoutError:
                continue
            if m is None:
                break
            msg = json.loads(m)
            if msg[0] == "stdout":
                out += msg[1]
        ws.close()
        return out

    out = asyncio.run(read())
    assert "Radeon Cloud:" in out and "rc-tunnel expose" in out, f"no tips in a JupyterLab terminal; got: {out[-300:]!r}"
    print("welcome: shown in a JupyterLab terminal")
finally:
    p.terminate()
PY
}
