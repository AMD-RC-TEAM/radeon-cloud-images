# RoboTwin · LingBot-VLA-v2

**Purpose line (English, one sentence; the start of the catalog description):**
RoboTwin 2.0 inference, closed-loop evaluation, LoRA training and full SFT for LingBot-VLA-v2 on Radeon Cloud W7900 GPUs.

This image provides the ROCm runtime and includes the workflow scripts, training configuration and three
compatibility patches from [RoboTwin-radeon-cloud at commit `f1683c77`](https://github.com/ZiguanWang/Robotwin-radeon-cloud/tree/f1683c77a0e1cea06f9beb03ba0a6c9e4261773b).
The project snapshot is stored at `/RoboTwin/RoboTwin-radeon-cloud` (without its `notebooks/`) and its patches are applied
during the build. The workshop notebooks are not in the image: the Radeon Cloud template clones
[RoboTwin-radeon-cloud](https://github.com/ZiguanWang/Robotwin-radeon-cloud) into `/workspace` and opens
`notebooks/sft_workshop.ipynb`, so notebook updates need no image rebuild.
The `requirements.txt` is pinned in this image directory; the patches come from the project snapshot. Model weights,
simulation assets and demonstrations are read from a separate, read-only platform mount; none are baked into the image.

| Component | Pinned source or runtime path |
| --- | --- |
| Base | `rocm/pytorch:rocm7.2.1_ubuntu24.04_py3.12_pytorch_release_2.9.1` at the digest in `Dockerfile` |
| Python and JupyterLab | `/opt/robotwin-env`: Python 3.12, JupyterLab 4.6.3; ROCm PyTorch 2.9.1 remains in the base `/opt/venv` |
| RoboTwin, XPolicyLab, LingBot-VLA-v2, AITER, FlashAttention and the project repository | Full commits in `Dockerfile`, downloaded as source snapshots and patched where needed |

## Quick start

For a manual Radeon Cloud instance, select this image, persistent `/workspace`, and the Devzone model mount. The mount
must expose `/models/robotwin-persistent/{assets,data,models}`. The matching project checkout is already in the image.
In a terminal:

```bash
test -f /RoboTwin/assets/objects/objaverse/list.json
test -f /RoboTwin/data/robotwin_demo_clean_joint_v30.txt
test -f /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models/robbyant_lingbot-vla-v2-6b/model.safetensors.index.json
test -f /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/scripts/eval/run_paired_eval.py
test -f /RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/training/lingbotvla_cli.yaml
python -c 'import sys, torch, jupyterlab; print(sys.executable, torch.__version__, jupyterlab.__version__)'
```

Launch from the workshop template to get the notebooks (`notebooks/sft_workshop.ipynb`, `notebooks/lora_workshop.ipynb`)
in `/workspace`; for a manual instance, clone the repository there. The image links
RoboTwin's experiment script directory and training YAML to the pinned project snapshot. Source
`/usr/local/bin/robotwin-env` when selecting GPUs for a shell job; it also creates `/workspace/runtime`, where outputs
and the Hugging Face cache belong.

| Read-only mount | Path used by RoboTwin |
| --- | --- |
| `/models/robotwin-persistent/assets` | `/RoboTwin/assets` |
| `/models/robotwin-persistent/data` | `/RoboTwin/data` |
| `/models/robotwin-persistent/models` | `/RoboTwin/experiments/lingbot_vla_v2_6b_robotwin/models` |

The image adds no argument-dispatching `ENTRYPOINT` or `CMD`; Radeon Cloud supplies the launch command. Outside the
platform, mount the read-only data at the same path and run `bash` or `jupyter lab` explicitly.

## What fits on disk

The image is approximately 49 GB uncompressed in a local Docker build, including the ROCm PyTorch base and model
runtime. The project code is small compared with the image. The prepared Devzone mount is separate:
approximately 16 GB of simulation assets, 38 GB of demonstrations
and converted data, and 51 GB of models (about 105 GB total). The source project's `scripts/data/prepare_external_data.sh`
prepares that external tree. The one-GPU LoRA workshop and four-GPU full SFT workshop need different instance sizes;
full SFT needs at least 100 GiB of free persistent output space. A full checkpoint can occupy about 70 GB under
`/workspace/runtime`. Check available space before training.

## How it is built

1. `Dockerfile` starts from a public ROCm PyTorch image pinned by tag and digest. It adds the system libraries used by
   SAPIEN/Vulkan, source builds and JupyterLab, without adding model weights or datasets.
2. `requirements.txt` pins the model, evaluator and JupyterLab packages. The Dockerfile installs the pinned build
   tools first, then installs the full list with `--no-deps --no-build-isolation` into `/opt/robotwin-env`. ROCm PyTorch
   remains in the base `/opt/venv`, and the build checks that it has not been replaced.
3. `fetch_src.py` downloads full-commit source snapshots of AITER, upstream FlashAttention, RoboTwin, XPolicyLab,
   LingBot-VLA-v2 and the project repository. The Dockerfile applies the three patches from that pinned project
   snapshot, installs the patched Python sources and checks key imports. AITER's package version is explicitly pinned
   because a codeload snapshot has no Git metadata for `setuptools_scm`.
4. The final layers link RoboTwin's asset, data and model paths to `/models/robotwin-persistent`, and link its scripts
   and training YAML to the included project snapshot. The platform supplies the launch command.

## Smoke

`smoke.sh` runs on one gfx1100 W7900D after the CI build. It checks the JupyterLab launch fast path, ROCm PyTorch on
the GPU, a small SAPIEN physics step, the three links into `/models/robotwin-persistent`, and a Jupyter server
answering HTTP. The standard CI worker does not mount Devzone data, so this smoke does not check mounted file
contents, load model weights, run a full RoboTwin scene, or perform training. A launch with the read-only mount is
needed to verify those paths before release.

## Release and catalog

1. The PR `validate` check parses the image and release settings. The `smoke` check builds with Kaniko and runs the
   checks above; both must pass before merging.
2. After a green build and smoke plus code-owner approval, merging releases `rc/robotwin-lingbot-vla-v2:rc-current`;
   the prior digest remains available as `rc-prev`.
3. The versions probe reports ROCm, Python and PyTorch. RoboTwin and LingBot-VLA-v2 source commits are pinned in the
   Dockerfile; this image adds no shared `versions_probe.py` change.
4. A new catalog row and Gallery template need an owner decision. The proposed workshop flow is a Gallery template
   pointing at a fixed-version row, with the GPU size, Devzone mount and persistent-space requirement in its
   description. rc-ops can verify a launch with the read-only mount on Global Test before wider availability.
