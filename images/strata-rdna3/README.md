# Strata · RDNA3 on Radeon PRO W7900 / W7900D (gfx1100)

Strata v0.2.13 (upstream `ghcr.io/niko1221/strata:0.2.13-rocm-gfx110x`, pinned by digest) with a gfx1100
DeepSeek engine (`strata-dsv41`) built in, JupyterLab, and one command per model. Weights are **not** in
the image. This image has not been built or run as an image yet; the DeepSeek numbers below come from
runs outside an image on 4× W7900D.

Start a server with one command; gfx1100 flags are already in the image:

```bash
strata-serve --model qwen3.6-35b-a3b-q4
# docker: docker run --device /dev/kfd --device /dev/dri -v <data>:/data -p 8080:8080 <image> --model qwen3.6-35b-a3b-q4
```

- `strata-serve --list` lists the presets. `strata-serve --plan --model <name>` prints the download and the
  `strata launch` line without starting.
- The first start downloads the pinned files to `/data/models/<name>` (through `HF_ENDPOINT` if set) and
  checks every sha256. Later starts reuse files whose size and hash still match.
- Extra flags after `--model` override the preset, the way `vllm serve` takes extra flags:
  `strata-serve --model deepseek-v4.1-flash-2.25 --speed full`.
- The server listens on port 8080 with OpenAI- and Anthropic-compatible APIs, plus `GET /health`.
- On a Radeon Cloud instance (no arguments → JupyterLab), run `strata-serve` in a terminal, then
  `rc-tunnel expose --port 8080` to reach the API from outside.
- A new model, patch, or gfx1100 preset ships as a **new image tag**. Update the image; the command stays
  `strata-serve --model <name>`.

| `--model` | GPUs | Download | Notes |
| --- | --- | --- | --- |
| `deepseek-v4.1-flash-2.25` | 4 | 274 GB | gfx1100 default: `--speed faster` (5 experts) and `--set prefill-chunk=1024`; `HSA_USERPTR_FOR_PAGED_MEM=0`, `DS4_FAST_ATTN=1`. Measured 2026-11-13 outside an image. |
| `deepseek-v4.1-flash-2.00` | 4 | 257 GB | Same gfx1100 default. Shares Engram / DSpark / Unsloth metadata with 2.25. Measured 2026-11-11 outside an image. |
| `qwen3.8-flash-next-iq3_s` | 2 | 83.6 GB | Ran on 2× W7900D before; not re-checked in this image. |
| `qwen3.6-35b-a3b-q4` | 1 | 22.9 GB | CI smoke model. Not yet run on W7900D as an image. |

DeepSeek file pins and the Qwen pins are copied from Strata v0.2.13 `setup.py`. `check_manifest.py` compares
them at build. Feed model updates are off (`STRATA_FEED_MODELS=0`).

Models download from Hugging Face; set `HF_ENDPOINT` to a mirror if huggingface.co is not reachable.
