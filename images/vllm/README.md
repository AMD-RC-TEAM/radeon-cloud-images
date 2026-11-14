# vLLM · Stable on Radeon PRO W7900 / W7900D (gfx1100)

vLLM 0.33.0 on ROCm 7.2 (upstream `vllm/vllm-openai-rocm`, pinned by digest in the Dockerfile), with a pinned
JupyterLab baked in. Start a server with the usual command; no extra flags are needed:

```bash
vllm serve Qwen/Qwen3-8B --host 0.0.0.0 --port 8000
```

This image changes one vLLM default (`rc_vllm_defaults.py`; an explicit flag always wins):
- **Attention backend: `ROCM_SEGMENTED_ATTN` on gfx11** when you don't pass `--attention-backend`, for ordinary
  decoder layers (head size 64/128/256, fp16/bf16 KV cache). For anything else, vLLM's own choice stands. Measured on
  W7900D with Qwen3-8B, time to first token at 32k context: TRITON_ATTN 26.7 s, ROCM_ATTN 18.4 s,
  ROCM_SEGMENTED_ATTN 13.0 s; accuracy on a 35B model was unchanged.
  To pick another backend, pass `--attention-backend TRITON_ATTN` (or `ROCM_ATTN`). `RC_VLLM_DEFAULTS=0` turns the
  default off entirely.

Models download from Hugging Face; set `HF_ENDPOINT` to a mirror if huggingface.co is not reachable.
