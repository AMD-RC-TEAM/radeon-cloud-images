# ComfyUI on Radeon PRO W7900 / W7900D (gfx1100)

A clean ComfyUI v0.45.0 (commit `989d93d0`) on ROCm 7.14.1 / PyTorch 2.12 / Python 3.12 (the PyTorch · Stable base),
with JupyterLab. No custom nodes, models or workflows are bundled.

- Start: `comfyui-start` (listens on 0.0.0.0:8188; `COMFY_PORT` changes the port; extra arguments go to ComfyUI).
- Models: put them in `/opt/ComfyUI/models/` (`checkpoints/`, `loras/`, `vae/`, ...). Outputs: `/opt/ComfyUI/output/`.
- Open it from your browser: `sh /var/run/secrets/frp-self-service/install` (once, in a Notebook terminal), then in a
  new terminal `rc-tunnel expose --port 8188`; it prints an https://rc-<id>.radeon.firstdg.ai address.
- Custom nodes: clone them into `/opt/ComfyUI/custom_nodes/` and restart ComfyUI.

Models download from Hugging Face; set `HF_ENDPOINT` to a mirror if huggingface.co is not reachable.
