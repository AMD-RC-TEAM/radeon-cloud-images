#!/bin/bash
# Smoke for the Ollama image on one W7900D: the Ollama server starts, answers, and finds the GPU through ROCm
# (an answering server alone also passes when Ollama silently falls back to the CPU). Also: the image's environment,
# including OLLAMA_MODELS, reaches SSH sessions.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
no_in_image_welcome
ssh_keeps_image_env

# ollama_env_over_ssh: OLLAMA_MODELS set in the image must reach an SSH session, both `ssh host cmd` and a login shell
# (what a user gets after logging in and running `ollama serve`). Same minimal sshd as ssh_keeps_image_env.
ollama_env_over_ssh() {
  if [ "$(id -u)" != 0 ]; then echo "ollama env over ssh: skipped (smoke not running as root)"; return 0; fi
  sshd_bin=$(command -v sshd 2>/dev/null || true); [ -n "$sshd_bin" ] || sshd_bin=/usr/sbin/sshd
  t=$(mktemp -d); port=2224
  ssh-keygen -q -t ed25519 -N '' -f "$t/hostkey" >/dev/null
  ssh-keygen -q -t ed25519 -N '' -f "$t/id" >/dev/null
  cp "$t/id.pub" "$t/authorized_keys"; chmod 600 "$t/authorized_keys"
  printf 'Port %s\nListenAddress 127.0.0.1\nHostKey %s/hostkey\nPidFile %s/sshd.pid\nUsePAM no\nPermitUserEnvironment no\nPasswordAuthentication no\nPermitRootLogin prohibit-password\nAuthorizedKeysFile %s/authorized_keys\nStrictModes no\nSetEnv RC_SMOKE=1\n' \
    "$port" "$t" "$t" "$t" > "$t/sshd_config"
  mkdir -p /run/sshd 2>/dev/null || true
  "$sshd_bin" -f "$t/sshd_config" || { rm -rf "$t"; echo "FAIL: sshd did not start"; return 1; }
  o="-p $port -i $t/id -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
  for i in $(seq 1 20); do ssh $o root@127.0.0.1 true 2>/dev/null && break; sleep 0.5; done
  rc=0
  want_models=/workspace/ollama/models
  want_bin=$(command -v ollama)
  got=$(ssh $o root@127.0.0.1 'printf %s "$OLLAMA_MODELS"' 2>&1) || true
  login=$(ssh $o root@127.0.0.1 "env -i HOME=/root PATH=/usr/bin:/bin bash -l -c 'printf %s \"\$OLLAMA_MODELS\"'" 2>&1) || true
  got_bin=$(ssh $o root@127.0.0.1 'command -v ollama' 2>&1) || true
  [ "$got" = "$want_models" ] || { echo "FAIL: ssh cmd OLLAMA_MODELS is '$got', image has '$want_models'"; rc=1; }
  [ "$login" = "$want_models" ] || { echo "FAIL: ssh login shell OLLAMA_MODELS is '$login', image has '$want_models'"; rc=1; }
  [ "$got_bin" = "$want_bin" ] || { echo "FAIL: ssh session finds ollama at '$got_bin', image has '$want_bin'"; rc=1; }
  kill "$(cat "$t/sshd.pid")" 2>/dev/null || true; rm -rf "$t"
  [ $rc = 0 ] && echo "ollama env over ssh: OLLAMA_MODELS=$want_models and ollama found for ssh cmd and login shells"
  return $rc
}
ollama_env_over_ssh

grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
command -v ollama
# Models go to /workspace/ollama/models at runtime; nothing is baked under /workspace.
[ "${OLLAMA_MODELS:-}" = /workspace/ollama/models ] || { echo "FAIL: OLLAMA_MODELS is '${OLLAMA_MODELS:-}'"; exit 1; }
test ! -e /workspace/ollama
# The server runs with a throwaway model directory so the smoke leaves nothing under /workspace.
(OLLAMA_MODELS=$(mktemp -d) ollama serve >/tmp/ollama.log 2>&1 &)
for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/version >/dev/null && break; sleep 2; done
curl -sf http://127.0.0.1:11434/api/version || { tail -40 /tmp/ollama.log; echo "FAIL: ollama serve did not answer"; exit 1; }
echo
# Ollama logs the GPU it found as: msg="inference compute" ... library=ROCm ... compute=gfx1100 ...
for i in $(seq 1 30); do grep -qiE 'inference compute.*library=rocm.*gfx1100' /tmp/ollama.log && break; sleep 2; done
grep -iE 'inference compute.*library=rocm.*gfx1100' /tmp/ollama.log || { tail -60 /tmp/ollama.log; echo "FAIL: ollama did not find the gfx1100 GPU through ROCm"; exit 1; }
pkill -f "ollama serve" 2>/dev/null || true
echo "SMOKE PASS"
