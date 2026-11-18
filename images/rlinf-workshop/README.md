# RLinf · Workshop

**Purpose line (English, one sentence; rc-ops uses it as the start of the picker description):**
RL fine-tuning of the Lingbot-VLA robot policy with GRPO on RoboTwin 2.0, for the RLinf workshop on 4 W7900D.

The environment of the RLinf workshop notebook ([github.com/Vivicai1005/rlinf-workshop](https://github.com/Vivicai1005/rlinf-workshop)):
participants train the Lingbot-VLA policy with GRPO on the RoboTwin 2.0 `place_shoe` task using
[RLinf](https://github.com/RLinf/RLinf), 40 steps on 4 GPUs, with an evaluation (success rate and videos) every 10 steps.

| | |
| --- | --- |
| Base | `rocm/dev-ubuntu-22.04:7.2-complete` (ROCm 7.2), pinned by digest |
| Python environment | `/opt/venv/lingbotvla`: Python 3.11.14, PyTorch 2.11.0+rocm7.2, SAPIEN 3.0.1, Lingbot-VLA, LeRobot, flash-attn 2.8.3 (ROCm), JupyterLab 4.6.6; first on `PATH` |
| RLinf | `/opt/RLinf`, commit `58d1b9ab` (RLinf main, with the ROCm RoboTwin support of RLinf/RLinf#1762) |
| RoboTwin | `/opt/robotwin`, commit `dca9ec68` (`RLinf_support` branch), with its assets in `/opt/robotwin/assets` |

No notebooks, models or datasets are in the image, and there is no `CMD`/`ENTRYPOINT` of its own.

## Quick start

On Radeon Cloud the workshop is launched from its Gallery notebook, which opens in `/workspace`. In a terminal of the
instance:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.device_count())"   # 2.11.0+rocm7.2 4
ls /data/models                                                                  # the three mounted models
source /opt/venv/lingbotvla/bin/activate                                         # what the notebook's training cells do
```

Outside the platform, the tools are on `PATH` (no argument-dispatching entrypoint); mount the models and a clone of the
workshop repository:

```bash
docker run --device /dev/kfd --device /dev/dri --group-add video --group-add render --shm-size 64g \
  -v /path/to/models:/data/models:ro -v /path/to/rlinf-workshop:/workspace -p 8888:8888 <image> \
  jupyter lab --notebook-dir=/workspace --ip=0.0.0.0 --port=8888 --allow-root --no-browser
```

## What fits on disk

- **Instance size:** 4 GPUs and ~200 GB of memory, with at least 8 GB of `/dev/shm` (a run uses ~0.2 GB; the
  Kubernetes default of 64 MiB is too small for 4-GPU training). A run uses only 5–8 CPU cores. It does not fit on
  1- or 2-GPU sizes.
- **Image:** ~57 GB uncompressed (~29 GB compressed): the ROCm 7.2 base (21.6 GB), the Python environment (21 GB), the
  RoboTwin assets (16 GB) and system packages for OpenGL/EGL/Vulkan rendering and video (0.7 GB).
- **Models** (read-only, 16.8 GB in total) are mounted by the platform as `/data/models/<name>` (the notebook also
  finds them one directory deeper or under `/models`). Only these files are read:

  | `<name>` | Hugging Face repository @ revision | Files |
  | --- | --- | --- |
  | `lingbot-vla-4b-posttrain-robotwin` | `robbyant/lingbot-vla-4b-posttrain-robotwin` @ `3e0c7c476bde3daaac00f79f3741a292a299f60a` | `model.safetensors`, `config.json`, `lingbotvla_cli.yaml` |
  | `Qwen2.5-VL-3B-Instruct` | `Qwen/Qwen2.5-VL-3B-Instruct` @ `66285546d2b821cf421d4f5eb2576359d3770cd3` | `config.json`, `generation_config.json`, `chat_template.json`, `preprocessor_config.json`, `tokenizer_config.json`, `tokenizer.json`, `vocab.json`, `merges.txt` |
  | `lingbot-vla-4b` | `robbyant/lingbot-vla-4b` @ `87712223fb463f0f6a6565f8feba64c35418e393` | `config.json` |

- **Workspace:** the notebooks come from the workshop repository; a run writes ~15 MB of logs and evaluation videos
  to `/workspace/rlinf_workshop`.

## Why the RoboTwin assets are in the image

This is an exception to "no model weights or datasets in the image", and the reason is time. RoboTwin's assets (16 GB:
object meshes, robot descriptions and background textures) are part of the simulator, not a dataset or a model: every
environment loads them at start-up and on each reset, and the workshop needs them before its first step. Downloading
them at launch would take tens of minutes per instance (they are served by Hugging Face's CDN), while the workshop is
timed so that the first evaluation arrives within 20 minutes of launch. They are pinned to a dataset revision and
checked by sha256.

## How it is built

The Dockerfile reproduces the environment of the RLinf ROCm RoboTwin image (RLinf's `docker/Dockerfile` with
`BUILD_TARGET=embodied-robotwin`, `PLATFORM=amd`, `ROCM_ARCHS=gfx1100`), reduced to what the workshop uses, from
pinned sources only:

| What | Pinned as | Fetched from (build argument to override) |
| --- | --- | --- |
| System packages | [`apt-packages.txt`](apt-packages.txt): the 392 packages the RLinf image adds to the base, exact versions | Ubuntu archive (`APT_MIRROR`, default `mirrors.aliyun.com`) |
| Python 3.11.14 | python-build-standalone 20260211, sha256 | `releases.astral.sh`, then GitHub Releases |
| Python packages | [`requirements.txt`](requirements.txt): 331 exact versions, installed with `--no-deps` | `PIP_INDEX_URL`; torch/torchvision `+rocm7.2` from `TORCH_INDEX_URL` (default the NJU mirror of download.pytorch.org) |
| flash-attn 2.8.3 for ROCm 7.2 | RLinf's prebuilt wheel, sha256 | GitHub Releases, through `gh-proxy.org` first (`GITHUB_PROXY`; the proxy Radeon Cloud's first-shell help suggests), then github.com |
| Lingbot-VLA (+ lingbot-depth, MoGe), LeRobot, RLinf, RoboTwin | commits | `codeload.github.com` ([`fetch.py`](fetch.py), with retries) |
| RoboTwin assets | dataset `TianxingChen/RoboTwin2.0` revision, sha256 per file | `HF_ENDPOINT` (default `hf-mirror.com`, which redirects to Hugging Face's CDN) |

Downloads are checked by sha256 wherever a file (not a commit) is fetched, so a mirror or proxy cannot change what is
installed. A stalled connection fails after 2 minutes and the next source is tried. Large files are fetched as
32 MB byte ranges over 8 parallel connections: Hugging Face's CDN serves ~5 MB/s per connection, and the 16 GB of
assets came down at ~31 MB/s this way (~9 minutes instead of ~55).

It then applies what RLinf's installer does for RoboTwin on AMD: two patches (SAPIEN's URDF loader, mplib's planner)
and four exports in the environment's `activate` script (RADV Vulkan driver, flash-attention's Triton AMD backend).

**Build time.** The large downloads are the torch wheel (6.2 GB) and the RoboTwin assets (16 GB). Whether the build
fits the 90-minute Kaniko deadline depends on how fast the build cluster reaches the NJU mirror and Hugging Face's CDN.

## Smoke

[`smoke.sh`](smoke.sh) checks, on one W7900D within the smoke Job's limits: the JupyterLab launch fast path; exactly one
gfx1100 and a bf16 matmul in PyTorch; that two RoboTwin `place_shoe` environments, built from RLinf's own workshop
config, reset (scene setup and rendering of the head and wrist cameras in SAPIEN/Vulkan) and step; and that JupyterLab
starts. It downloads nothing and takes ~25 s. SAPIEN's "Failed to initialize denoiser" lines and a curobo
`ImportError` traceback in its output are expected (CUDA-only features that the workshop does not use).

## Validation

The environment this Dockerfile reproduces was validated on a W7900D server with the platform's limits imitated
(`--cpus=64 --memory=200g --shm-size=64g`, models at `/data/models` with only the files above, notebooks in
`/workspace`): the workshop notebook ran its 40 steps, the first evaluation (after step 10) arrived 17:46 after launch,
the whole notebook took 54:25, and the evaluation success rates after steps 10/20/30/40 were 0.97/0.81/0.97/0.94
(32 episodes each); peak memory 165 GB (including page cache), `/dev/shm` use 0.2 GB, 5 CPU cores on average. The smoke
above, run with the smoke Job's limits (one GPU's device nodes, `--cpus=8 --memory=48g`, default `/dev/shm`), passed
in 23 s.

**In progress:** the image built from this Dockerfile is being compared file by file (Python environment, interpreter,
RLinf, RoboTwin and its assets, system packages) with the validated image above, and its smoke run with the smoke
Job's limits; the result will be added here.

## How it reaches the picker

1. **PR check:** `validate` parses the Dockerfile; `smoke` mirrors the base, builds with Kaniko and runs `smoke.sh`.
2. **Merge:** one code-owner Approve; the release moves `rc/rlinf-workshop:rc-current` to the new digest.
3. **Versions:** the probe reports ROCm 7.2.0, Python 3.11 and PyTorch 2.11.0.
4. **Catalog:** this is a new row, so it needs an owner decision. Users need it for the RLinf workshop: the Gallery
   notebook of the workshop launches with this image on a 4-GPU size with the three models mounted. The Gallery
   template should point at a fixed-version row of this image, as the repository README asks for templates.
