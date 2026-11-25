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

# torch_gemm_floor: plain fp32 and bf16 matmuls with the image's default settings must reach a minimum speed on the
# W7900D (gfx1100). On gfx1100, torch's default BLAS library (hipBLASLt) runs fp32 GEMM at ~2.6 TFLOPS against ~22 for
# rocBLAS, which made fp32 training ~3x slower (2026-11-24). Images set TORCH_BLAS_PREFER_HIPBLASLT=0 to get rocBLAS;
# this check fails if that setting is lost or a library upgrade regresses. Measured on 8 images at 4096^3: fp32 22-23
# TFLOPS with rocBLAS vs 2.6 with hipBLASLt, so a floor of 12 catches the slow path with room for card-to-card noise.
# bf16 measured 80-84 (rocBLAS) and 66-70 (hipBLASLt); its floor of 60 only catches a large half-precision regression,
# since the fp32 floor already catches the library choice. Override GEMM_FLOOR_FP32 / GEMM_FLOOR_BF16 only to re-measure.
torch_gemm_floor() {
  python3 - "${GEMM_FLOOR_FP32:-12}" "${GEMM_FLOOR_BF16:-60}" <<'PY'
import sys, time, torch
floors = {torch.float32: float(sys.argv[1]), torch.bfloat16: float(sys.argv[2])}
n, fails = 4096, []
for dt, floor in floors.items():
    a, b = torch.randn(n, n, device="cuda", dtype=dt), torch.randn(n, n, device="cuda", dtype=dt)
    best = 0.0
    for _ in range(3):                      # best of 3 timed runs, so one slow sample does not fail the smoke
        a @ b; torch.cuda.synchronize(); t = time.perf_counter()
        for _ in range(20): a @ b
        torch.cuda.synchronize(); best = max(best, 2 * n**3 * 20 / (time.perf_counter() - t) / 1e12)
    print(f"gemm {str(dt)[6:]} {n}^3: {best:.1f} TFLOPS (floor {floor}), blas={torch.backends.cuda.preferred_blas_library()}")
    if best < floor:
        fails.append(f"{str(dt)[6:]} {best:.1f} < {floor}")
assert not fails, "FAIL: GEMM below floor (is TORCH_BLAS_PREFER_HIPBLASLT=0 set?): " + "; ".join(fails)
PY
}

# cpu_threads_match_limit: CPU thread pools follow the container's CPU limit, not the host's core count (numpy matmul
# was 2.5-3x slower on a 16-CPU instance without it, 2026-11-25), a user's own setting wins, and the start-up hook can
# never break Python: unreadable cgroup files fall back to the CPU affinity mask, a broken hook module is ignored silently.
cpu_threads_match_limit() {
  want=$(awk '$1!="max"{n=int($1/$2); print (n<1?1:n)}' /sys/fs/cgroup/cpu.max 2>/dev/null); [ -n "$want" ] || want=$(nproc)
  got=$(env -u OMP_NUM_THREADS -u OPENBLAS_NUM_THREADS -u MKL_NUM_THREADS python3 -c 'import os,torch;print(os.environ.get("OMP_NUM_THREADS"),os.environ.get("OPENBLAS_NUM_THREADS"),os.environ.get("MKL_NUM_THREADS"),torch.get_num_threads())')
  [ "$got" = "$want $want $want $want" ] || { echo "FAIL: python threads '$got', want $want x4"; return 1; }
  sh_got=$(env -i HOME=/root PATH=/usr/bin:/bin bash -l -c 'echo $OMP_NUM_THREADS $OPENBLAS_NUM_THREADS $MKL_NUM_THREADS')
  [ "$sh_got" = "$want $want $want" ] || { echo "FAIL: login shell threads '$sh_got', want $want x3"; return 1; }
  user=$(env -u OPENBLAS_NUM_THREADS -u MKL_NUM_THREADS OMP_NUM_THREADS=3 python3 -c 'import os,torch;print(os.environ.get("OPENBLAS_NUM_THREADS"),os.environ.get("MKL_NUM_THREADS"),torch.get_num_threads())')
  [ "$user" = "3 3 3" ] || { echo "FAIL: user OMP_NUM_THREADS=3 not followed: '$user'"; return 1; }
  nocg=$(python3 - <<'PY'
import builtins, os
real = builtins.open
def deny(f, *a, **k):
    if str(f).startswith("/sys/fs/cgroup"): raise PermissionError(f)
    return real(f, *a, **k)
builtins.open = deny
import rc_cpu_threads as r
print(r.cpu_limit() == len(os.sched_getaffinity(0)))
PY
)
  [ "$nocg" = "True" ] || { echo "FAIL: unreadable cgroup files did not fall back to the affinity mask ($nocg)"; return 1; }
  t=$(mktemp -d); echo 'raise RuntimeError("broken hook")' > "$t/rc_cpu_threads.py"
  broken=$(PYTHONPATH=$t python3 -c 'print("ok")' 2>&1); rm -rf "$t"
  [ "$broken" = "ok" ] || { echo "FAIL: a broken hook module affected Python start-up: '$broken'"; return 1; }
  echo "cpu threads: $want (CPU limit) in python, torch and login shells; user setting wins; hook fail-safe"
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

# ssh_keeps_image_env: an SSH session must see the image's python3 (e.g. /opt/venv/bin/python3), both for
# `ssh host cmd` and for a fresh login shell, and must import torch when the image's python3 can. sshd runs
# the way Radeon Cloud starts it (app/ssh_runtime.py): UsePAM no, PermitUserEnvironment no, one SetEnv line.
ssh_keeps_image_env() {
  if [ "$(id -u)" != 0 ]; then echo "ssh session PATH: skipped (smoke not running as root)"; return 0; fi
  sshd_bin=$(command -v sshd 2>/dev/null || true); [ -n "$sshd_bin" ] || sshd_bin=/usr/sbin/sshd
  want=$(command -v python3)
  t=$(mktemp -d); port=2223
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
  got=$(ssh $o root@127.0.0.1 'command -v python3' 2>&1) || true
  login=$(ssh $o root@127.0.0.1 'env -i HOME=/root PATH=/usr/bin:/bin bash -l -c "command -v python3"' 2>&1) || true
  [ "$got" = "$want" ] || { echo "FAIL: ssh host cmd python3 is '$got', image has '$want'"; rc=1; }
  [ "$login" = "$want" ] || { echo "FAIL: ssh login shell python3 is '$login', image has '$want'"; rc=1; }
  if python3 -c 'import torch' 2>/dev/null; then
    ssh $o root@127.0.0.1 "python3 -c 'import torch'" || { echo "FAIL: import torch fails over ssh"; rc=1; }
  fi
  kill "$(cat "$t/sshd.pid")" 2>/dev/null || true; rm -rf "$t"
  [ $rc = 0 ] && echo "ssh session env: python3 = $want and torch loads for ssh cmd and login shells"
  return $rc
}
