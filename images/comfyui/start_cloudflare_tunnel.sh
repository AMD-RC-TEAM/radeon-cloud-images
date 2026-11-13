#!/bin/bash
set -e

export COMFY_PORT=${COMFY_PORT:-8188}

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "[tunnel] cloudflared not found" >&2
  exit 1
fi

echo "[tunnel] starting Cloudflare Tunnel for http://127.0.0.1:${COMFY_PORT}"
echo "[tunnel] after start, copy the *.trycloudflare.com URL from logs"

exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${COMFY_PORT}"
