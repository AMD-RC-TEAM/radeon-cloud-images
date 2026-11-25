#!/bin/bash
ulimit -c 0; export HSA_DISABLE_COREDUMP_ON_EXCEPTION=1 HOME=/tmp; cd /tmp
echo "cgroup cpu.max: $(cat /sys/fs/cgroup/cpu.max)  nproc: $(nproc)"
for r in 1 2; do echo "BEFORE $r"; timeout -s KILL 900 python3 -u /t/measure.py 2>&1 | grep M_JSON; done
mkdir -p /tmp/inst && cp /t/rc_cpu_threads.py /t/rc_cpu_threads.pth /t/zz-rc-cpu-threads.sh /t/install.sh /tmp/inst/ && sh /tmp/inst/install.sh
for r in 1 2; do echo "AFTER $r"; timeout -s KILL 900 python3 -u /t/measure.py 2>&1 | grep M_JSON; done
echo "== what each process sees"
echo "python:            $(python3 -c 'import os,torch;print(os.environ.get("OMP_NUM_THREADS"), torch.get_num_threads())' 2>/dev/null)"
echo "python -I:         $(python3 -I -c 'import os;print(os.environ.get("OMP_NUM_THREADS"))')"
echo "user export 4:     $(OMP_NUM_THREADS=4 python3 -c 'import os,torch;print(os.environ.get("OMP_NUM_THREADS"), os.environ.get("OPENBLAS_NUM_THREADS"), os.environ.get("MKL_NUM_THREADS"), torch.get_num_threads())' 2>/dev/null)"
echo "login shell:       $(env -i HOME=/root PATH=/usr/bin:/bin bash -l -c 'echo $OMP_NUM_THREADS $OPENBLAS_NUM_THREADS $MKL_NUM_THREADS')"
echo "interactive shell: $(env -i HOME=/root PATH=/usr/bin:/bin bash -i -c 'echo $OMP_NUM_THREADS' 2>/dev/null)"
echo "non-interactive (as sshd runs host cmds, bashrc sourced via SSH_CLIENT): $(env -i HOME=/root PATH=/usr/bin:/bin SSH_CLIENT='1 2 3' bash -c 'echo ${OMP_NUM_THREADS-unset}')"
echo "shell user export: $(env -i HOME=/root PATH=/usr/bin:/bin OMP_NUM_THREADS=3 bash -l -c 'echo $OMP_NUM_THREADS $OPENBLAS_NUM_THREADS $MKL_NUM_THREADS')"
echo "RUN DONE"
