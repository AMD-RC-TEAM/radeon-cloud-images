# Launch-bound training: tiny MLP, batch 8, many small kernels. Prints steps/s.
import torch, time, json, os, sys
torch.manual_seed(0)
m = torch.nn.Sequential(*[l for _ in range(12) for l in (torch.nn.Linear(256,256), torch.nn.GELU(), torch.nn.LayerNorm(256))]).cuda()
dt = torch.float32 if sys.argv[1] == "fp32" else torch.bfloat16
opt = torch.optim.AdamW(m.parameters(), lr=1e-4)
x = torch.randn(8,256,device="cuda"); y = torch.randn(8,256,device="cuda")
def step():
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=dt!=torch.float32):
        loss = torch.nn.functional.mse_loss(m(x), y)
    loss.backward(); opt.step(); opt.zero_grad(set_to_none=True)
for _ in range(30): step()
torch.cuda.synchronize(); t=time.perf_counter(); n=300
for _ in range(n): step()
torch.cuda.synchronize(); el=time.perf_counter()-t
print("LAUNCH_JSON", json.dumps({"mode": sys.argv[1], "env": {k: os.environ.get(k) for k in ("HSA_NO_SCRATCH_RECLAIM","HIP_FORCE_DEV_KERNARG")}, "steps_s": round(n/el,1)}), flush=True)
