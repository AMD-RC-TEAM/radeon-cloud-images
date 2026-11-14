# SGLang on Radeon PRO W7900 / W7900D (gfx1100)

SGLang (commit `51b27f7`, August 2026) with the RDNA3 plugin `sglang-radeon-rdna3` 0.2.0 and `sgl-kernel` built for
gfx1100, on ROCm 7.2.4 / PyTorch 2.10. LLM serving and SGLang-Diffusion (image generation).

Start a server with the usual command; no extra flags are needed in this image:

```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 30000
# or: sglang serve --model-path Qwen/Qwen2.5-7B-Instruct --host 0.0.0.0 --port 30000
```

This image changes two SGLang defaults (`rc_sglang_defaults.py`; an explicit flag always wins):
- the attention backend defaults to `triton` (SGLang's ROCm default, aiter, is for Instinct GPUs and fails on gfx1100);
- CUDA/HIP graphs are **off**, because graph capture hangs on gfx1100. Throughput is therefore not tuned; do not
  use this image for benchmarks that assume graphs. `RC_SGLANG_CUDA_GRAPH=1` leaves SGLang's own setting.

Models download from Hugging Face; set `HF_ENDPOINT` to a mirror if huggingface.co is not reachable.

## Image generation (SGLang-Diffusion)

```bash
sglang serve --model-path Qwen/Qwen-Image-2.1 --host 0.0.0.0 --port 30010
curl http://127.0.0.1:30010/v1/images/generations -H 'Content-Type: application/json' \
  -d '{"prompt": "a red apple on a wooden table", "size": "1024x1024", "n": 1}'
```
- On one Radeon PRO W7900D (48 GB; checked by the image smoke): Qwen-Image-2.1 (7.1B parameters, about 15 GB in bf16) fits on one card
  without offload. Larger diffusion models may need `--component-residency text_encoder=component-offload` or more cards.
- Qwen-Image-2.1 is not in this SGLang version's native model list; it runs through SGLang's generic diffusers path,
  which is why the image carries diffusers 0.43 (SGLang's own pin, 0.37, predates that model).
- Output format: in this image, a request without `output_format` returns PNG. Upstream SGLang defaults to JPEG, which
  fails with HTTP 500 for models that return images with an alpha channel, such as Qwen-Image. Asking for
  `"output_format": "jpeg"` explicitly still hits that upstream bug with those models; use `png` or `webp`.
- Not included because they are CUDA-only: `nvidia-modelopt` (NVFP4/FP8 quantized checkpoints), `st_attn` and `vsa`
  (sparse/sliding-tile attention backends). Models that need them do not run here.

