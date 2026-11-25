# Ollama on Radeon PRO W7900 / W7900D (gfx1100)

Ollama 0.40.18, installed from the official release archives `ollama-linux-amd64.tar.zst` and
`ollama-linux-amd64-rocm.tar.zst` (pinned by SHA-256 in the Dockerfile) into `/usr`, on ROCm 7.2 (upstream
`rocm/pytorch`, pinned by digest), with a pinned JupyterLab baked in.
Start the server with the usual command:

```bash
ollama serve
```

In another terminal, check that it is running:

```bash
ollama -v
```

## Where models go

`OLLAMA_MODELS` is set to `/workspace/ollama/models`, so models are kept on `/workspace` and survive an instance
restart when you choose "Persistent /workspace" at launch (without it, they are lost with the instance, like everything
else outside `/workspace`). The directory is created by `ollama serve` the first time it runs, not in the image. The variable is also set in SSH
sessions, so `ollama serve` started after logging in over SSH uses the same directory.
Set `OLLAMA_MODELS` to another path if you want models somewhere else.

No model is included. `ollama pull` downloads from the Ollama registry, which can be slow or not reachable from some
sites.
