# Example · Hello (worked example, never released)

**Purpose line (English, one sentence; rc-ops uses it as the start of the picker description):**
A tiny PyTorch image that shows the parts every Radeon Cloud image needs.

> This directory exists only in a draft PR that shows how to add an image. It is never merged; merging to `main` releases.

## Quick start
In a Radeon Cloud instance started from this image, open a terminal:

```bash
python3 -c "import torch; print(torch.cuda.get_device_name(0))"   # one W7900D
jupyter lab --version
```

Outside the platform, the tools are on PATH; there is no argument-dispatching entrypoint:

```bash
docker run --device /dev/kfd --device /dev/dri <image> python3 -c "import torch; print(torch.cuda.is_available())"
```

## What fits on disk
- The image is the upstream PyTorch image plus JupyterLab and one small package. There are no models in it.
- If your image's workflow downloads models or datasets, list the realistic sizes here and say which instance sizes they fit on. Downloads go to the user's volume at runtime, through `HF_ENDPOINT` on the platform.

## How it reaches the picker
1. **PR check:** `validate` checks the layout and that `FROM` is a public upstream pinned by digest. `smoke` mirrors the upstream, builds with Kaniko and runs [`smoke.sh`](smoke.sh) on one W7900D.
2. **Merge:** one code-owner Approve, then merge. [`tools/release.py`](../../tools/release.py) moves `rc/<name>:rc-current` to the new digest and keeps the previous one as `rc-prev`.
3. **Versions:** after the smoke, the release runs [`tools/versions_probe.py`](../../tools/versions_probe.py) in the image and logs `RC-VERSIONS-OF <digest> {...}`. ROCm, Python and PyTorch are detected automatically. If your image's main tool isn't one of `ORDER` in that file, add a line there in the same PR.
4. **Catalog (rc-ops, outside CI):**
   - For a new image, rc-ops/rc-ux create the stable picker row (`catalog_row` in [`image.yaml`](image.yaml)), tracking `rc/<name>:rc-current`. Name, stable or latest, and picker visibility are set there.
   - Adding a new row to the picker needs an owner decision, so say in the PR why users need it.
   - `catalog_sync` then adopts each new digest on Global Test first and runs a launch check, then Global and China.
   - It writes the row description as `<purpose line> · ROCm … · Python … · PyTorch …`.
