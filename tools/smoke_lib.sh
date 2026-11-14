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

# welcome_once: the first-shell help prints once in an interactive shell, never in `bash -c`, and not again.
# The block ends with the "Hide this message" line; the image's own bashrc may print other lines before it.
WELCOME_END='Hide this message: touch ~/.rc-welcome-hidden'
welcome_block() { sed 's/\x1b\[[0-9;]*m//g' | grep -F -B200 "$WELCOME_END" || true; }
welcome_once() {
  local h first; h=$(mktemp -d)
  [ -z "$(HOME=$h bash -c 'true' 2>&1 | welcome_block)" ] || { echo "FAIL: welcome printed in a non-interactive shell"; return 1; }
  first=$(HOME=$h bash -i -c 'true' 2>/dev/null | welcome_block)
  [ -n "$first" ] || { echo "FAIL: no welcome in the first interactive shell"; return 1; }
  grep -q 'rc-tunnel expose --port' <<<"$first" || { echo "FAIL: no tunnel line in the help"; return 1; }
  grep -q '^  No GitHub?' <<<"$first" || { echo "FAIL: no Downloads block in the help"; return 1; }
  [ "$(printf '%s\n' "$first" | awk 'length > 80' | wc -l)" -eq 0 ] || { echo "FAIL: help line wider than 80 columns"; return 1; }
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

    def new_terminal():
        req = urllib.request.Request(f"{base}/api/terminals?token={tok}", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=10))["name"]

    async def read(name, until, send=None, wait=10):
        ws = await websocket_connect(f"ws://127.0.0.1:{port}/terminals/websocket/{name}?token={tok}")
        out, t0, sent = "", time.time(), False
        while time.time() - t0 < wait and until not in out:
            if send and not sent and time.time() - t0 > 3:
                await ws.write_message(json.dumps(["stdin", send])); sent = True
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

    # The first terminal shows the tips, and its shell is bash (the image sets SHELL=/bin/bash; unset, it is sh).
    # The marker is assembled by the shell, so the echoed command line itself never contains "RC-SHELL=".
    probe = 'echo "RC-$(echo SHELL)=$(basename "$(readlink -f /proc/$$/exe)")"\r'
    out = asyncio.run(read(name, "RC-SHELL=", send=probe, wait=15))
    assert "Hide this message" in out and "rc-tunnel expose" in out, f"no help in a JupyterLab terminal; got: {out[-300:]!r}"
    assert "RC-SHELL=bash" in out, f"JupyterLab terminal is not bash; got: {out[-200:]!r}"
    print("welcome: shown in a JupyterLab terminal; the terminal shell is bash")
    # A second terminal in the same home does not repeat them.
    out2 = asyncio.run(read(new_terminal(), "RC-SHELL=", send=probe, wait=15))
    assert "RC-SHELL=" in out2, f"second JupyterLab terminal did not answer; got: {out2[-200:]!r}"
    assert "Hide this message" not in out2, "welcome printed again in a second JupyterLab terminal"
    print("welcome: not repeated in a second JupyterLab terminal")
finally:
    p.terminate()
PY
}

# rc_tunnel_shim: rc-tunnel is on PATH from the first shell; outside an instance (no secret bundle) it says so and exits 1.
rc_tunnel_shim() {
  [ "$(command -v rc-tunnel)" = /usr/local/bin/rc-tunnel ] || { echo "FAIL: rc-tunnel shim not on PATH"; return 1; }
  local h out; h=$(mktemp -d)
  if out=$(HOME=$h rc-tunnel version 2>&1); then echo "FAIL: shim succeeded without a secret bundle"; return 1; fi
  grep -q 'not available here' <<<"$out" || { echo "FAIL: unexpected shim message: $out"; return 1; }
  # With an installer: the first call installs, shows nothing of the installer on stdout, and passes the arguments on;
  # a failing installer's output reaches the user.
  local fake; fake=$(mktemp -d)
  cat > "$fake/ok" <<'SH'
#!/bin/sh
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\necho "real rc-tunnel: $*"\n' > "$HOME/.local/bin/rc-tunnel"; chmod 755 "$HOME/.local/bin/rc-tunnel"
echo "installer chatter"
SH
  printf '#!/bin/sh\necho "broker unreachable" >&2; exit 7\n' > "$fake/bad"
  h=$(mktemp -d)
  out=$(HOME=$h RC_TUNNEL_INSTALLER=$fake/ok rc-tunnel expose --port 8888 2>/dev/null) || { echo "FAIL: shim did not run the installed binary"; return 1; }
  [ "$out" = "real rc-tunnel: expose --port 8888" ] || { echo "FAIL: shim output: $out"; return 1; }
  out=$(HOME=$h RC_TUNNEL_INSTALLER=$fake/bad rc-tunnel status 2>/dev/null) || { echo "FAIL: shim reinstalled over an installed binary"; return 1; }
  h=$(mktemp -d)
  if out=$(HOME=$h RC_TUNNEL_INSTALLER=$fake/bad rc-tunnel status 2>&1); then echo "FAIL: shim ignored a failing installer"; return 1; fi
  grep -q 'broker unreachable' <<<"$out" || { echo "FAIL: installer error hidden: $out"; return 1; }
  echo "rc-tunnel shim: on PATH; explains itself outside an instance; installs once, passes arguments, shows installer errors"
}
