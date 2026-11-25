#!/bin/bash
# Alternate default / FAST, two rounds, each in a fresh process with MIOpen's per-user caches cleared (like a new instance).
ulimit -c 0; export HSA_DISABLE_COREDUMP_ON_EXCEPTION=1 HOME=/tmp/h; cd /tmp
for r in 1 2; do for mode in default FAST; do
  rm -rf /tmp/h; mkdir -p /tmp/h
  if [ $mode = default ]; then unset MIOPEN_FIND_MODE; else export MIOPEN_FIND_MODE=FAST; fi
  timeout -s KILL 1500 python3 -u /m/sweep.py 2>&1 | grep -E "SWEEP_JSON|Error|error:" | tail -2
done; done
echo "RUN DONE"
