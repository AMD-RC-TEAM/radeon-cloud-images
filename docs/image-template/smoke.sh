#!/bin/bash
# Smoke for <name> on one W7900D. Runs inside the image; must print "SMOKE PASS" last.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
# Test what users do with this image, e.g. a GPU op, a server answering one request, or a few training steps.
echo "SMOKE PASS"
