# Ollama on Radeon PRO W7900 / W7900D (gfx1100)

Ollama 0.40.18, installed from the official release archives `ollama-linux-amd64.tar.zst` and
`ollama-linux-amd64-rocm.tar.zst` (pinned by SHA-256 in the Dockerfile) into `/usr`, with a pinned JupyterLab baked in.
Start the server with the usual command:

```bash
ollama serve
```

In another terminal, check that it is running:

```bash
ollama -v
```
