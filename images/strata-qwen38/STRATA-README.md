# Qwen3.8-Flash-Next on this W7900D (Strata)

This instance runs **Strata**, our inference engine for Radeon RDNA3, serving **Qwen3.8-Flash-Next** (IQ3_XXS) on its GPU through an **OpenAI-compatible API**. The server starts by itself when the instance starts. The first start takes about 1-2 minutes.

**Quick test:** open `strata-quicktest.ipynb` and run all cells. It waits until the server is ready, lists the model, and sends one chat request with its speed.

**From your own code in this instance** (notebook, terminal or SSH), use any OpenAI client:
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="unused")
print(client.chat.completions.create(model="Qwen3.8-Flash-Next-IQ3_XXS",
      messages=[{"role": "user", "content": "Hello"}]).choices[0].message.content)
```
**From the browser:** the same API is at your notebook's URL prefix + `proxy/8080/v1`, behind your Radeon Cloud login.

**Who can reach it:** only this instance and that proxy. The server listens on 127.0.0.1 and is not exposed to the internet, so no API key is needed inside the instance.

**Speed (measured on this instance size, 1 GPU):** one user ~110 tok/s (Chinese) and ~134 tok/s (code). Two parallel requests reach ~130-148 tok/s together.

**If something is wrong:** the server log is `/tmp/b0-logs/autostart.log`. Health: `curl -s http://127.0.0.1:8080/health` (ready when `"loaded": true`). To restart it, restart the instance.
