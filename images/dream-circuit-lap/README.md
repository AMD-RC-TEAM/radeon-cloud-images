# Dream Circuit Lap

**Purpose line (English, one sentence; the start of the catalog description):**
The Dream Circuit Lap course on Radeon Cloud W7900 GPUs: design a fictional race track and film one onboard lap with ComfyUI, Qwen Image 2.1 and MiniMax H3.

ComfyUI v0.45.0 (commit `989d93d0`) on ROCm 7.14.1 / PyTorch 2.12 / Python 3.12 (the PyTorch · Stable base), with
JupyterLab and what the course's `notebooks/cloud.ipynb` (and `cloud_en.ipynb`) expects to find. The course is not in
the image: the Radeon Cloud template clones [dream-circuit-lap](https://github.com/wangxunx/dream-circuit-lap) into
`/workspace`, so course updates need no image rebuild.

| Component | Pinned source or runtime path |
| --- | --- |
| ComfyUI | `/opt/ComfyUI` (`COMFY_DIR`), packages in `requirements.txt` (the same set as `images/comfyui`) |
| Cloud nodes | `custom_nodes/ComfyUI-AMD-Qwen-Image-2.1` and `custom_nodes/ComfyUI-AMD-MiniMaxH3`, commits in `Dockerfile` |
| Car edit models (17 GB) | `models/{diffusion_models,text_encoders,vae}/`, Comfy-Org/Qwen-Image-2.1 files in `models.txt` |
| Media and fonts | `/opt/dream-circuit-lap/{media,fonts}` (`DREAM_CIRCUIT_MEDIA_CACHE`, `F1_FONT_REGULAR`, `F1_FONT_BOLD`), from the course's `media/manifest.json` at `COURSE_COMMIT` (kept as `/opt/dream-circuit-lap/manifest.json`) |

- Start: run the notebook's setup cells; `scripts/start_comfyui_cloud.sh` starts ComfyUI on 8188 and exposes it with
  rc-tunnel.
- Keyframes and videos run on the H3 gateway (an H3 key from https://h3.oneclickamd.ai, saved to
  `/opt/ComfyUI/user/h3_gateway_api_key.txt` by the notebook); only the car edit runs on the local GPU.
- Updating the course's nodes or media: bump `QWEN_NODE_COMMIT`, `H3_NODE_COMMIT` or `COURSE_COMMIT` in `Dockerfile`.
