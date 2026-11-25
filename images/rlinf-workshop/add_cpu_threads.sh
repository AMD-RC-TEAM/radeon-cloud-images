#!/bin/sh
# Size CPU thread pools (OMP/OPENBLAS/MKL_NUM_THREADS) to the instance's CPU limit instead of the host's core count.
# A 16-CPU instance sees the host's 128 CPUs; numpy/PyTorch then run 64-128 threads and numpy matmul was ~2.5x slower
# (measured 2026-11-25). Installs a fail-safe Python start-up hook (.pth) into the image's Python and a shell snippet for
# terminals and SSH. A user's own setting always wins. Same file in every image directory (each image builds from its
# own directory); keep the copies identical.
set -eu
sp=$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
cat > "$sp/rc_cpu_threads.py" <<'RC_EOF'
"""Size CPU thread pools to the container's CPU limit, not the host's core count.

Inside a Radeon Cloud instance os.cpu_count() reports the host (e.g. 128) while the container may use only its CPU
limit (16 on the 1-GPU template). numpy/OpenBLAS and torch then start 64-128 threads that fight over 16 CPUs; numpy
matmul measured 2.7-3.6x slower than with 16 threads (2026-11-25). Loaded at Python start-up by rc_cpu_threads.pth,
before numpy or torch read these variables. Never overrides the user: if any of the three is set, the others take that value, so `export OMP_NUM_THREADS=..`
always wins. The same rule is applied to shells by /etc/profile.d/zz-rc-cpu-threads.sh.
"""
import os

VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")


def cpu_limit():
    """CPUs this container may use: cgroup v2 cpu.max, then cgroup v1 quota/period, then the CPU affinity mask."""
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()[:2]
        if quota != "max":
            return max(1, int(int(quota) // int(period)))
    except (OSError, ValueError):
        pass
    try:
        quota = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        period = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        if quota > 0 and period > 0:
            return max(1, quota // period)
    except (OSError, ValueError):
        pass
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return None


def apply():
    # If the user set any of them, use their value for the rest too: torch takes MKL_NUM_THREADS over
    # OMP_NUM_THREADS, so filling MKL with the CPU limit would silently override a user's OMP_NUM_THREADS.
    user = next((os.environ[v] for v in VARS if os.environ.get(v)), None)
    n = user or cpu_limit()
    if n:
        for v in VARS:
            os.environ.setdefault(v, str(n))


try:
    apply()
except BaseException:   # never break or print anything at interpreter start-up; the .pth line also guards the import
    pass
RC_EOF
cat > "$sp/rc_cpu_threads.pth" <<'RC_EOF'
import os; exec("try:\n import rc_cpu_threads\nexcept BaseException:\n pass")
RC_EOF
cat > /etc/profile.d/zz-rc-cpu-threads.sh <<'RC_EOF'
# Size CPU thread pools to the container's CPU limit for shells (terminals, SSH); see rc_cpu_threads.py for why.
# Never overrides the user: if any of the three is set, the others take that value.
# If the user set any of them, the others follow that value (torch prefers MKL_NUM_THREADS over OMP_NUM_THREADS).
_rc_n=${OMP_NUM_THREADS:-${OPENBLAS_NUM_THREADS:-${MKL_NUM_THREADS:-}}}
[ -n "$_rc_n" ] || _rc_n=$(awk '$1!="max"{n=int($1/$2); print (n<1?1:n)}' /sys/fs/cgroup/cpu.max 2>/dev/null)
[ -n "$_rc_n" ] || _rc_n=$(nproc 2>/dev/null)
if [ -n "$_rc_n" ]; then
  for _rc_v in OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS; do
    eval "[ -n \"\${$_rc_v+x}\" ] || export $_rc_v=$_rc_n"
  done
fi
unset _rc_n _rc_v
RC_EOF
chmod 0644 "$sp/rc_cpu_threads.py" "$sp/rc_cpu_threads.pth" /etc/profile.d/zz-rc-cpu-threads.sh
# Prepend: Ubuntu's bash.bashrc returns early for non-interactive shells (ssh host commands), as keep_image_env.sh notes.
rc=/etc/bash.bashrc; line='[ -r /etc/profile.d/zz-rc-cpu-threads.sh ] && . /etc/profile.d/zz-rc-cpu-threads.sh  # rc-cpu-threads'
if [ -f "$rc" ]; then
  grep -qF '# rc-cpu-threads' "$rc" || { printf '%s\n' "$line" | cat - "$rc" > "$rc.new" && cat "$rc.new" > "$rc" && rm -f "$rc.new"; }
else
  printf '%s\n' "$line" > "$rc"
fi
env -u OMP_NUM_THREADS -u OPENBLAS_NUM_THREADS -u MKL_NUM_THREADS python3 -c 'import os, rc_cpu_threads; print("add_cpu_threads.sh: hook in", rc_cpu_threads.__file__, "(build host limit", os.environ.get("OMP_NUM_THREADS"), ")")'
