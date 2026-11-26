#!/bin/bash
# Smoke for the Strata image on one W7900D. CI has no copy of the 78 GB model, so serving is tested on the test sites.
# Here: the usual Jupyter/SSH checks; every engine library resolves; the engine's Python server imports; both Jupyter
# extensions are enabled; a real Jupyter server starts with the autostart extension, which skips cleanly without a
# model; and its jupyter-server-proxy route /proxy/8080/ answers.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
ssh_keeps_image_env
no_in_image_welcome
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
test "$(readlink -f /opt/b0/current)" = /opt/b0/v3.1
! ldd /opt/b0/current/bin/strata | grep "not found"
/opt/strata/venv/bin/python -c 'import sys; sys.path.insert(0, "/opt/strata/control"); import serve.server; print("strata server imports")'
ext=$(jupyter server extension list 2>&1)
grep -qE 'rc_strata_autostart .*enabled' <<<"$ext" || { echo "FAIL: rc_strata_autostart not enabled"; echo "$ext"; exit 1; }
grep -qE 'jupyter_server_proxy .*enabled' <<<"$ext" || { echo "FAIL: jupyter_server_proxy not enabled"; echo "$ext"; exit 1; }
t=$(mktemp -d); log=$t/jupyter.log
(cd "$t" && B0_MODEL=$t/no-model B0_LOG=$t/b0 jupyter server --no-browser --port 18888 --ServerApp.token=smoke --ServerApp.root_dir="$t" >"$log" 2>&1 &)
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null && break; sleep 1; done
curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null || { tail -40 "$log"; echo "FAIL: jupyter server did not start"; exit 1; }
grep -q "model not mounted" "$t/b0/autostart.log" || { cat "$t/b0/autostart.log" 2>/dev/null; echo "FAIL: autostart did not record the missing model"; exit 1; }
test -f "$t/strata-quicktest.ipynb" -a -f "$t/STRATA-README.md" || { echo "FAIL: quick-start files not copied"; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:18888/proxy/8080/health?token=smoke")
case "$code" in 5*) echo "proxy route answers ($code: nothing on 8080 without a model, as expected)";; *) echo "FAIL: proxy route gave $code"; exit 1;; esac
pkill -f "jupyter-server --no-browser --port 18888|jupyter server --no-browser --port 18888" || true; rm -rf "$t"
echo "SMOKE PASS"
