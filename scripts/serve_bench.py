# Client: throughput at concurrency 16 (64 requests) and batch-1 decode, fixed 256 output tokens, ~512-token prompts.
import json, sys, time, urllib.request, concurrent.futures as cf, random
port = int(sys.argv[1]); words = "alpha beta gamma delta epsilon river mountain cloud engine paper silver window".split()
def req(seed):
    r = random.Random(seed); prompt = " ".join(r.choice(words) for _ in range(500))
    body = {"model": "m", "prompt": prompt, "max_tokens": 256, "min_tokens": 256, "ignore_eos": True, "temperature": 0}
    t = time.perf_counter()
    out = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions",
          data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}), timeout=600))
    return out["usage"]["completion_tokens"], time.perf_counter() - t
req(0)  # warmup
t = time.perf_counter()
with cf.ThreadPoolExecutor(16) as ex: res = list(ex.map(req, range(1, 65)))
wall = time.perf_counter() - t
n1, t1 = req(999)
print("SERVE_JSON", json.dumps({"c16_out_tok_s": round(sum(r[0] for r in res) / wall, 1), "b1_decode_tok_s": round(n1 / t1, 1)}), flush=True)
