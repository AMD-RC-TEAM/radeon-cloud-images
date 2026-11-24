#!/bin/bash
# Runs inside the pod. Separate processes for env variants, alternated ABAB.
ulimit -c 0; export HSA_DISABLE_COREDUMP_ON_EXCEPTION=1 HOME=/tmp; cd /tmp
echo "== env"; for v in TORCH_BLAS_PREFER_HIPBLASLT HSA_NO_SCRATCH_RECLAIM HIP_FORCE_DEV_KERNARG OMP_NUM_THREADS; do echo "$v=${!v-<unset>}"; done
echo "== blas"; timeout -s KILL 1500 python3 -u /bench/blas.py
echo "== launch"; for r in 1 2 3; do for mode in fp32 bf16; do
  timeout -s KILL 300 env -u HSA_NO_SCRATCH_RECLAIM -u HIP_FORCE_DEV_KERNARG python3 -u /bench/launch.py $mode
  timeout -s KILL 300 env HSA_NO_SCRATCH_RECLAIM=1 HIP_FORCE_DEV_KERNARG=1 python3 -u /bench/launch.py $mode; done; done
echo "== hf"; for prec in fp32 bf16; do for b in 1 0; do
  timeout -s KILL 900 env TORCH_BLAS_PREFER_HIPBLASLT=$b python3 -u /bench/hf.py $prec 2>&1 | grep -E "HF_JSON|Error|error" ; done; done
echo "RUN DONE"
