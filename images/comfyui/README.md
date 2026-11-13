# ComfyUI on Radeon PRO W7900 / W7900D (gfx1100)

ComfyUI v0.45.0 (commit `989d93d0`) on ROCm 7.14.1 / PyTorch 2.12 / Python 3.12 (the PyTorch · Stable base), with a
pinned JupyterLab. Same layout and entry points as the earlier ComfyUI image:

| What | Where |
|---|---|
| ComfyUI | `/comfyui_workspace/ComfyUI` (models in `models/`, outputs in `output/`) |
| Start ComfyUI on port 8188 (`COMFY_PORT`) | `/usr/local/bin/start_comfyui_no_default_workflow.sh` |
| JupyterLab on 8888 (the image entrypoint) | `/start_notebook.sh` (runs `/workspace/startup_hook.sh` or `/comfyui_workspace/startup_hook.sh` first if present) |
| sshd, then your command | `/start.sh <command>` |
| Cloudflare quick tunnel for 8188 | `/usr/local/bin/start_cloudflare_tunnel.sh` |
| Custom nodes | `/comfyui_workspace/ComfyUI/custom_nodes` (ComfyUI-CacheDiT included) |
| Python | `/opt/venv` |

To share ComfyUI from a Radeon Cloud instance, prefer Radeon Cloud's own tunnel (see the first-terminal tips):
`sh /var/run/secrets/frp-self-service/install`, then in a new terminal `rc-tunnel expose --port 8188`.

Models download from Hugging Face; set `HF_ENDPOINT` to a mirror if huggingface.co is not reachable.
