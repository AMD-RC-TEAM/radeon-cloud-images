# RLinf · Workshop

**Purpose line (English, one sentence; rc-ops uses it as the start of the picker description):**
RL fine-tuning of the Lingbot-VLA robot policy with GRPO on RoboTwin 2.0, for the RLinf workshop on 4 W7900D.

The environment of the RLinf workshop notebook ([github.com/Vivicai1005/rlinf-workshop](https://github.com/Vivicai1005/rlinf-workshop)),
on 2026-11-29: participants train the Lingbot-VLA policy with GRPO on the RoboTwin 2.0 `place_shoe` task using
[RLinf](https://github.com/RLinf/RLinf), 40 steps on 4 GPUs, with an evaluation (success rate and videos) every 10 steps.

| | |
| --- | --- |
| Base | `rocm/dev-ubuntu-22.04:7.2-complete` (ROCm 7.2), pinned by digest |
| Python environment | `/opt/venv/lingbotvla`: Python 3.11.14, PyTorch 2.11.0+rocm7.2, Triton 3.5.1, SAPIEN 3.0.1, Lingbot-VLA, LeRobot, flash-attn 2.8.3 (ROCm), JupyterLab 4.6.6; first on `PATH` |
| RLinf | `/opt/RLinf`, commit `58d1b9ab` (RLinf main, with the ROCm RoboTwin support of RLinf/RLinf#1762) |
| RoboTwin | `/opt/robotwin`, commit `dca9ec68` (`RLinf_support` branch); its assets are read from the data volume |

No notebooks, models, datasets or simulation assets are in the image, and there is no `CMD`/`ENTRYPOINT` of its own.

## The data volume

The models and RoboTwin's assets are read from one read-only volume mounted at **`/models/rlinf-workshop`** (~33 GB):

| Path in `/models/rlinf-workshop` | Source (Hugging Face, pinned revision) | Size |
| --- | --- | --- |
| `lingbot-vla-4b-posttrain-robotwin/` | `robbyant/lingbot-vla-4b-posttrain-robotwin` @ `3e0c7c47`: `model.safetensors`, `config.json`, `lingbotvla_cli.yaml` | 16.8 GB |
| `Qwen2.5-VL-3B-Instruct/` | `Qwen/Qwen2.5-VL-3B-Instruct` @ `66285546`: `config.json`, `generation_config.json`, `chat_template.json`, `preprocessor_config.json`, `tokenizer_config.json`, `tokenizer.json`, `vocab.json`, `merges.txt` | 11 MB |
| `lingbot-vla-4b/` | `robbyant/lingbot-vla-4b` @ `87712223`: `config.json` | 294 B |
| `robotwin-assets/` | dataset `TianxingChen/RoboTwin2.0` @ `981c92aa`: `background_texture.zip`, `objects.zip`, `embodiments.zip`, unpacked (without `__MACOSX`) | 16 GB |

[`mount/prepare_mount.sh`](https://github.com/Vivicai1005/rlinf-workshop/blob/main/mount/prepare_mount.sh) in the
workshop repository builds exactly this directory: it downloads every file at its pinned revision (through
`HF_ENDPOINT`, default hf-mirror.com) and checks it by sha256; nothing is generated afterwards. In the image,
`/opt/robotwin/assets/{background_texture,objects,embodiments}` are links into `robotwin-assets/`, and the notebook
finds the models under `/models/rlinf-workshop/<name>`. RoboTwin only reads the assets (the workshop uses the mplib
planner, so no curobo configuration is written into them); this was checked with the assets mounted read-only.

There is no training dataset: GRPO generates its data online in the simulator.

## Quick start

On Radeon Cloud the workshop is launched from its Gallery notebook, which opens in `/workspace`. In a terminal of the
instance:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.device_count())"   # 2.11.0+rocm7.2 4
ls /models/rlinf-workshop                                                       # the three models and robotwin-assets
ls /opt/robotwin/assets/objects | head -3                                       # assets reached through the links
```

Outside the platform, the tools are on `PATH` (no argument-dispatching entrypoint); mount the data volume and a clone of
the workshop repository:

```bash
docker run --device /dev/kfd --device /dev/dri --group-add video --group-add render --shm-size 64g \
  -v /path/to/rlinf-workshop-data:/models/rlinf-workshop:ro -v /path/to/rlinf-workshop:/workspace -p 8888:8888 <image> \
  jupyter lab --notebook-dir=/workspace --ip=0.0.0.0 --port=8888 --allow-root --no-browser
```

## What fits on disk

- **Instance size:** 4 GPUs and ~200 GB of memory, with at least 8 GB of `/dev/shm` (a run uses ~0.2 GB; the
  Kubernetes default of 64 MiB is too small for 4-GPU training). A run uses only 5–8 CPU cores. It does not fit on
  1- or 2-GPU sizes.
- **Image:** ~41 GB uncompressed (~15 GB compressed): the ROCm 7.2 base (21.6 GB), the Python environment (21 GB) and
  system packages for OpenGL/EGL/Vulkan rendering and video (0.7 GB).
- **Data volume:** ~33 GB, read-only (above).
- **Workspace:** the notebooks come from the workshop repository; a run writes ~15 MB of logs and evaluation videos
  to `/workspace/rlinf_workshop`.
- **`/tmp`:** on Radeon Cloud it is a 4 GB tmpfs, too small for the ~3 GB of temporary GPU-compiler (comgr) files that
  the four training workers write at start-up. The notebook therefore sets `TMPDIR` and `RAY_TMPDIR` to
  `/workspace/.tmp` for the training run; `/tmp` stays nearly empty.

## How it is built

The Dockerfile reproduces the environment of the RLinf ROCm RoboTwin image (RLinf's `docker/Dockerfile` with
`BUILD_TARGET=embodied-robotwin`, `PLATFORM=amd`, `ROCM_ARCHS=gfx1100`), reduced to what the workshop uses, from
pinned sources only:

| What | Pinned as | Fetched from (build argument to override) |
| --- | --- | --- |
| System packages | [`apt-packages.txt`](apt-packages.txt): the 60 packages the RLinf image installs (dependencies resolved by apt) | Ubuntu archive (`APT_MIRROR`, default `mirrors.aliyun.com`) |
| Python 3.11.14 | python-build-standalone 20260211, sha256 | `registry.npmmirror.com` (a mirror of the GitHub releases), then `releases.astral.sh`, then GitHub Releases |
| Python packages | [`requirements.txt`](requirements.txt): 325 exact versions, installed with `--no-deps` | `PIP_INDEX_URL` |
| PyTorch ROCm 7.2 wheels | [`torch-wheels.txt`](torch-wheels.txt): torch, torchvision, triton, pytorch-triton-rocm, triton-rocm, by file name and sha256 | `TORCH_WHEELS_MIRROR` (default the NJU mirror), then download.pytorch.org |
| flash-attn 2.8.3 for ROCm 7.2 | RLinf's prebuilt wheel, sha256 | GitHub Releases, through `gh-proxy.com` first (`GITHUB_PROXY`), then github.com |
| Lingbot-VLA (+ lingbot-depth, MoGe), LeRobot, RLinf, RoboTwin | commits | `codeload.github.com` ([`fetch.py`](fetch.py), with retries) |

Every fetched file (not a commit) is checked by sha256, so a mirror or proxy cannot change what is installed. A stalled
connection fails after 2 minutes and the next source is tried; large files are fetched as 32 MB byte ranges over 8
parallel connections. Three of the PyTorch wheels provide the `triton` module; they are installed one at a time in the
order of `torch-wheels.txt`, which reproduces the validated environment's `triton` (3.5.1 on top). Then the build applies
RLinf's patches for RoboTwin on AMD (SAPIEN's URDF loader, mplib's planner), and sets the RADV Vulkan driver and
flash-attention's Triton AMD backend as `ENV`, so that Jupyter kernels get them too.

Three more settings keep the tools and the logs clean on AMD:

- **`amd-smi` works as typed.** The environment's `amdsmi` Python package is the base image's own (AMD SMI 26.2, from
  `/opt/rocm/share/amd_smi`) instead of PyPI's newest one up to ROCm 7.2, which is 7.0.2: with the environment first on
  `PATH`, the `amd-smi` command runs with its Python and needs the bindings of its own release.
- **No denoiser in RoboTwin's cameras.** RoboTwin asks SAPIEN's ray tracer for the OIDN denoiser, whose bundled build
  is CUDA-only; on AMD it failed for every camera (two error lines each time, ~14,500 per workshop run) and the images
  were rendered without it. The Dockerfile sets it to `"none"`; the images are the same, pixel for pixel.
- **`AMDGPU_ASIC_ID_TABLE_PATHS`** points PyTorch's own `libdrm_amdgpu` to the `amdgpu.ids` in the torch wheel, so HIP
  start-up no longer prints `(null): No such file or directory` once per GPU, and the GPU's name is
  "AMD Radeon Pro W7900D".

The first CI build of this image (with the RoboTwin assets still inside) took ~40 minutes in Kaniko.

## Smoke

[`smoke.sh`](smoke.sh) checks, on one W7900D within the smoke Job's limits: the JupyterLab launch fast path; exactly one
gfx1100, a bf16 matmul in PyTorch, Triton 3.5.1 and the RADV/flash-attention settings; the asset links and that RLinf's
RoboTwin environment imports. When the data volume is mounted at `/models/rlinf-workshop`, it also builds two RoboTwin
`place_shoe` environments from RLinf's own workshop config, resets them (scene setup and rendering of the head and
wrist cameras in SAPIEN/Vulkan) and steps them; without the volume it says so and skips that part. It also runs
`amd-smi version`, checks that HIP start-up prints no `(null): No such file or directory` and shows the GPU's name, and
that the RoboTwin environments print no "Failed to initialize denoiser". It downloads nothing. A curobo `ImportError`
traceback in its output is expected (a CUDA-only planner that the workshop does not use).

## Validation

All runs on a W7900D server with the platform's limits imitated (`--cpus=64 --memory=200g --shm-size=64g`, the data
volume mounted read-only at `/models/rlinf-workshop`, the notebooks in `/workspace`), 32 evaluation episodes each.

| Image | First evaluation | Whole notebook | Evaluation success after steps 10/20/30/40 |
| --- | --- | --- | --- |
| The validated RLinf image this Dockerfile reproduces | 17:46 after launch | 54:25 | 0.97 / 0.81 / 0.97 / 0.94 |
| This Dockerfile, previous revision (`e2d5b54`) | 18:01 | 54:10 | 0.97 / 0.88 / 1.00 / 0.94 |
| **This revision** (`amdsmi`, denoiser, `AMDGPU_ASIC_ID_TABLE_PATHS`; `/tmp` a 4 GB tmpfs as on Radeon Cloud) | ~17:30 | in progress | 0.97 / 0.91 / 0.88 / … |

Peak memory 170–180 GB (including page cache), `/dev/shm` use 0.2 GB, 5–8 CPU cores on average. In this revision's run,
`train.log` has no denoiser, `cudaError` or `(null): No such file or directory` lines (previously ~14,500 and 128),
`/tmp` stayed at 1 MB and `/workspace/.tmp` peaked at 2.2 GB during start-up.

**The image** (built on the same kind of server, 25 minutes, from the previous revision plus these changes; the
maintainers' later changes on `main`, openssh and download sources, do not touch the training): compared file by file
with the previous revision's image (~114,000 entries), the only differences are the `amdsmi` package (7.0.2 → 26.2.1), uv's install metadata and
one newer Ubuntu security update (`linux-libc-dev`). The previous revision had been compared the same way with the
validated image: in the Python environment, interpreter, RLinf and RoboTwin, 102,248 files had identical content; the
rest were install metadata, the exports moved from `activate` to `ENV`, four `crcmod`/`evdev` extension modules
compiled at install time, and the asset links; the same 716 system packages, four at newer security versions.
`smoke.sh` with the smoke Job's limits passed without the data volume (9 s; environment check skipped) and with it mounted read-only (26 s;
reset 14 s, step 1 s; `amd-smi` 26.2.1, "AMD Radeon Pro W7900D").

## How it reaches the picker

1. **PR check:** `validate` parses the Dockerfile; `smoke` mirrors the base, builds with Kaniko and runs `smoke.sh`.
2. **Merge:** one code-owner Approve; the release moves `rc/rlinf-workshop:rc-current` to the new digest.
3. **Versions:** the probe reports ROCm 7.2.0, Python 3.11 and PyTorch 2.11.0.
4. **Catalog:** a Gallery template for the workshop notebook, pointing at a fixed-version row of this image, with a
   4-GPU size and the data volume mounted at `/models/rlinf-workshop`; not a stable picker row.
