#!/bin/bash
cd /tmp; export HOME=/tmp
echo "torch $(python3 -c 'import torch;print(torch.__version__)' 2>/dev/null) python $(command -v python3)"
echo "no hook, OMP=7 only:  torch threads $(env -u MKL_NUM_THREADS -u OPENBLAS_NUM_THREADS OMP_NUM_THREADS=7 python3 -c 'import torch;print(torch.get_num_threads())' 2>/dev/null)"
echo "no hook, MKL=5 only:  torch threads $(env -u OMP_NUM_THREADS -u OPENBLAS_NUM_THREADS MKL_NUM_THREADS=5 python3 -c 'import torch;print(torch.get_num_threads())' 2>/dev/null)"
echo "no hook, none:        torch threads $(env -u OMP_NUM_THREADS -u OPENBLAS_NUM_THREADS -u MKL_NUM_THREADS python3 -c 'import torch;print(torch.get_num_threads())' 2>/dev/null)"
mkdir -p /tmp/inst && cp /t/rc_cpu_threads.py /t/rc_cpu_threads.pth /t/zz-rc-cpu-threads.sh /t/install.sh /tmp/inst/ && sh /tmp/inst/install.sh >/dev/null && echo "hook installed"
. /t/smoke_cpu_threads.sh; cpu_threads_match_limit && echo "SMOKE CASE PASS" || echo "SMOKE CASE FAIL"
