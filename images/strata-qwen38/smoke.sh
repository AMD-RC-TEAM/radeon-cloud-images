#!/bin/bash
# Smoke for the Strata image on one W7900D. CI has no copy of the 78 GB model, so serving is tested on the test sites.
# (The smoke runs as root, hence --allow-root; instances run Jupyter as the platform starts it.)
# Here: the usual Jupyter/SSH checks; every engine library resolves; the engine's Python server imports; both Jupyter
# extensions are enabled; no notebooks are baked in; a real Jupyter server starts with the autostart extension, which
# skips cleanly without a model and writes nothing into the notebook root; its jupyter-server-proxy route /proxy/8080/ answers.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
ssh_keeps_image_env
no_in_image_welcome
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
test "$(readlink -f /opt/b0/current)" = /opt/b0/v3.1
! ldd /opt/b0/current/bin/strata | grep "not found"
# The notebook comes from the template's repository clone, not from the image (as for the workshop images).
test ! -e /opt/strata-quickstart
test -z "$(find /opt/strata /opt/b0 /workspace -name "*.ipynb" 2>/dev/null | head -1)" || { echo "FAIL: notebook baked into the image"; exit 1; }
/opt/strata/venv/bin/python -c 'import sys; sys.path.insert(0, "/opt/strata/control"); import serve.server; print("strata server imports")'
ext=$(jupyter server extension list 2>&1)
grep -qE 'rc_strata_autostart .*enabled' <<<"$ext" || { echo "FAIL: rc_strata_autostart not enabled"; echo "$ext"; exit 1; }
grep -qE 'jupyter_server_proxy .*enabled' <<<"$ext" || { echo "FAIL: jupyter_server_proxy not enabled"; echo "$ext"; exit 1; }
t=$(mktemp -d); log=$t/jupyter.log
(cd "$t" && B0_MODEL=$t/no-model B0_LOG=$t/b0 jupyter server --no-browser --allow-root --ServerApp.allow_remote_access=True --port 18888 --IdentityProvider.token=smoke --ServerApp.root_dir="$t" >"$log" 2>&1 &)
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null && break; sleep 1; done
curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null || { tail -40 "$log"; echo "FAIL: jupyter server did not start"; exit 1; }
grep -q "model not mounted" "$t/b0/autostart.log" || { cat "$t/b0/autostart.log" 2>/dev/null; echo "FAIL: autostart did not record the missing model"; exit 1; }
test -z "$(ls -A "$t" | grep -vE "^(jupyter.log|b0)$")" || { ls -A "$t"; echo "FAIL: the image wrote files into the notebook root"; exit 1; }
# What the server behind the proxy sees: a tiny echo server on 8080 stands in for the engine (no model in CI).
python3 -c '
import http.server, json
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        b = json.dumps({"path": self.path, "host": self.headers.get("Host")}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", 8080), H).serve_forever()' &
ECHO=$!; sleep 1
# A public Host, as instances are reached through the gateway (the platform's Jupyter allows remote access, as here).
seen=$(curl -s -w '\n%{http_code}' -H "Host: instance.example" "http://127.0.0.1:18888/proxy/8080/v1/models?token=smoke")
code=${seen##*$'\n'}; seen=${seen%$'\n'*}
[ "$code" = 200 ] || { kill $ECHO; echo "FAIL: request via the proxy gave HTTP $code: ${seen:0:300}"; tail -20 "$log"; exit 1; }
kill $ECHO; wait $ECHO 2>/dev/null || true
echo "behind the proxy the server sees: $seen"
grep -q '"path": "/v1/models' <<<"$seen" || { echo "FAIL: proxy did not strip /proxy/8080/"; exit 1; }
test "$(printenv STRATA_ALLOWED_HOSTS)" = "*" || { echo "FAIL: STRATA_ALLOWED_HOSTS must be * (the forwarded Host may be the instance's)"; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:18888/proxy/8080/health?token=smoke")
case "$code" in 5*) echo "proxy route answers ($code: nothing on 8080 without a model, as expected)";; *) echo "FAIL: proxy route gave $code"; exit 1;; esac
pkill -f "jupyter-server --no-browser --port 18888|jupyter server --no-browser --port 18888" || true; rm -rf "$t"
echo "SMOKE PASS"
