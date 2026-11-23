#!/bin/bash
# Smoke the ROCm runtime and SAPIEN physics on one W7900D; model data is mounted by the platform at launch.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
no_in_image_welcome
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
test -L /RoboTwin/assets
test -L /RoboTwin/data
test -L /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models
test "$(readlink /RoboTwin/assets)" = /models/robotwin-persistent/assets
test "$(readlink /RoboTwin/data)" = /models/robotwin-persistent/data
test "$(readlink /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models)" = /models/robotwin-persistent/models
python - <<'PY'
import sys
import torch, sapien, mplib, lerobot, lingbotvla, jupyterlab
assert sys.executable.startswith("/opt/robotwin-env/"), sys.executable
assert torch.__file__.startswith("/opt/venv/"), torch.__file__
assert torch.version.hip and torch.cuda.is_available()
assert torch.cuda.get_device_properties(0).gcnArchName.startswith("gfx1100")
a = torch.arange(1024, device="cuda", dtype=torch.float32)
assert float((a * a).sum().item()) == 357389824.0
scene = sapien.Scene()
scene.set_timestep(1 / 240)
actor = scene.create_actor_builder().build_kinematic(name="smoke")
actor.set_pose(sapien.Pose([0, 0, 0]))
scene.step()
print("RoboTwin ROCm and SAPIEN smoke passed")
PY
jupyter lab --no-browser --ip=127.0.0.1 --port=18888 --ServerApp.token=smoke --allow-root >/tmp/robotwin-jupyter.log 2>&1 &
jupyter_pid=$!
trap 'kill "$jupyter_pid" 2>/dev/null || true' EXIT
for i in $(seq 1 30); do
  if curl -fsS 'http://127.0.0.1:18888/api/status?token=smoke' >/dev/null; then break; fi
  sleep 1
done
curl -fsS 'http://127.0.0.1:18888/api/status?token=smoke' >/dev/null || { tail -50 /tmp/robotwin-jupyter.log; exit 1; }
echo "SMOKE PASS"
