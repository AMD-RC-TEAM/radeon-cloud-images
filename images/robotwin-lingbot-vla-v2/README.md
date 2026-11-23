# RoboTwin · LingBot-VLA-v2

RoboTwin 2.0 inference, evaluation, LoRA training and full SFT for LingBot-VLA-v2 on Radeon Cloud W7900 GPUs.

This image adapts the `docker/external-data` runtime in [RoboTwin-radeon-cloud](https://github.com/ZiguanWang/Robotwin-radeon-cloud). It pins the public ROCm PyTorch base by digest, the RoboTwin, LingBot-VLA-v2, AITER and upstream FlashAttention source commits, and the Python requirements. All five source trees are downloaded as fixed-commit snapshots from GitHub codeload; AITER's package version is pinned explicitly because the snapshot has no Git metadata for `setuptools_scm`. The three ROCm compatibility patches are included as top-level files. Models, simulation assets and datasets are read from the platform's read-only mount. The workflow scripts, training configuration and notebooks stay in the project repository instead of being duplicated in this image.

## Quick start

Select this image with a W7900 GPU instance, **Persistent /workspace**, and the **Devzone** model mount. The mount must contain `/models/robotwin-persistent/{assets,data,models}`. Copy the matching `RoboTwin-radeon-cloud` project tree to `/workspace/RoboTwin-radeon-cloud` before running its scripts or notebooks. In a terminal:

```bash
test -f /RoboTwin/assets/objects/objaverse/list.json
test -f /RoboTwin/data/robotwin_demo_clean_joint_v30.txt
test -f /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models/robbyant_lingbot-vla-v2-6b/model.safetensors.index.json
test -f /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/scripts/eval/run_paired_eval.py
test -f /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/training/lingbotvla_cli.yaml
python -c 'import sys, torch, jupyterlab; print(sys.executable, torch.__version__, jupyterlab.__version__)'
```

Open the notebooks under `/workspace/RoboTwin-radeon-cloud/notebooks` in JupyterLab. The image links `/RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/scripts` and its training YAML to the project tree in `/workspace`; the notebooks use these paths. Keep the complete project tree because the notebooks call scripts from several subdirectories. `python` and `jupyter` use `/opt/robotwin-env`, while ROCm PyTorch remains in the base `/opt/venv`. Source `/usr/local/bin/robotwin-env` when selecting GPUs for a shell job. Training output and Hugging Face cache go under `/workspace/runtime`.

The mount layout matches the source repository's `external-data` image:

| Platform mount | Runtime path |
| --- | --- |
| `/models/robotwin-persistent/assets` | `/RoboTwin/assets` |
| `/models/robotwin-persistent/data` | `/RoboTwin/data` |
| `/models/robotwin-persistent/models` | `/RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models` |

The image has no argument-dispatching entrypoint; Radeon Cloud supplies the launch command. Outside the platform, mount both the read-only data and the project repository at the paths above and run `bash` or `jupyter lab` explicitly.

## What fits on disk

The image includes patched RoboTwin and LingBot-VLA-v2 source and one Python environment for model code and JupyterLab, but no model weights, simulation assets, demonstrations, notebooks or project scripts. The Devzone mount holds the 50 `demo_clean` tasks, converted LeRobot data, RoboTwin simulation assets, and LingBot-VLA-v2 model files. On the current mount these occupy about 105 GB combined; keep them off the persistent `/workspace` volume. A full SFT checkpoint can be about 70 GB, so check free space under `/workspace/runtime` before training. The full depth and video teacher configuration targets 4 or 8 W7900 GPUs with 48 GiB each; the CI smoke uses one GPU.

## Source and verification

The requirements and patches in this directory reflect the local `RoboTwin-radeon-cloud` working tree on 2026-11-23. The base image is pinned at `sha256:96a2fb24dec9896e2f8238178f0c49d0dcc4c7dcc597be09e4564316bd86d191`; upstream source commits are recorded in the Dockerfile. CI checks JupyterLab in the model environment, gfx1100, a ROCm PyTorch operation, a small SAPIEN physics step, the mount-path links and a notebook server. The CI worker does not mount Devzone data, so it cannot prove that the external project scripts, assets or model weights execute together. A launch with the read-only mount and project tree is required before release.

A local build on 2026-11-23 passed using the official PyPI index. With the current read-only mount and project tree, a local gfx1201 container passed a PyTorch GPU operation, a SAPIEN physics step and the JupyterLab server check after selecting the GPU's PCI-form `DRI_PRIME` value. This does not cover model inference or training, or the CI worker's gfx1100 build and smoke.
