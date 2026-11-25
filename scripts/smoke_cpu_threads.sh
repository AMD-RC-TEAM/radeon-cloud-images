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
