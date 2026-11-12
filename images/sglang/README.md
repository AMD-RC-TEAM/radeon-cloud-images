# SGLang on Radeon PRO W7900 / W7900D (gfx1100)

SGLang (commit `51b27f7`, August 2026) with the RDNA3 plugin `sglang-radeon-rdna3` 0.2.0 and `sgl-kernel` built for
gfx1100, on ROCm 7.2.4 / PyTorch 2.10. LLM serving; SGLang-Diffusion is not included.

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
