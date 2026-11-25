# One process = one MIOPEN_FIND_MODE setting. Cold first-step time (caches cleared by run.sh) and steady speed.
import os, sys, time, json, torch, torchvision
torch.backends.cudnn.benchmark = False
def timed(step, warm=10, n=30):
    torch.cuda.synchronize(); t = time.perf_counter(); step(); torch.cuda.synchronize(); first = time.perf_counter() - t
    for _ in range(warm): step()
    torch.cuda.synchronize(); t = time.perf_counter()
    for _ in range(n): step()
    torch.cuda.synchronize(); return round(first, 2), round((time.perf_counter() - t) / n * 1000, 2)
res = {"mode": os.environ.get("MIOPEN_FIND_MODE", "default"), "torch": torch.__version__}
def train(model, bs, dtype, size=224):
    m = model.cuda(); opt = torch.optim.SGD(m.parameters(), lr=0.01)
    x = torch.randn(bs, 3, size, size, device="cuda"); y = torch.randint(0, 1000, (bs,), device="cuda")
    def step():
        with torch.autocast("cuda", dtype=dtype, enabled=dtype != torch.float32):
            loss = torch.nn.functional.cross_entropy(m(x), y)
        loss.backward(); opt.step(); opt.zero_grad(set_to_none=True)
    return step
res["resnet50_bf16_bs64_train"] = timed(train(torchvision.models.resnet50(), 64, torch.bfloat16))
res["resnet50_fp32_bs32_train"] = timed(train(torchvision.models.resnet50(), 32, torch.float32))
class Block(torch.nn.Module):                      # Stable-Diffusion-UNet-like resnet block
    def __init__(s, c): super().__init__(); s.n1 = torch.nn.GroupNorm(32, c); s.c1 = torch.nn.Conv2d(c, c, 3, padding=1); s.n2 = torch.nn.GroupNorm(32, c); s.c2 = torch.nn.Conv2d(c, c, 3, padding=1)
    def forward(s, x): return x + s.c2(torch.nn.functional.silu(s.n2(s.c1(torch.nn.functional.silu(s.n1(x))))))
class UNetish(torch.nn.Module):
    def __init__(s):
        super().__init__(); s.inp = torch.nn.Conv2d(4, 320, 3, padding=1)
        s.d = torch.nn.ModuleList([Block(320), torch.nn.Conv2d(320, 640, 3, 2, 1), Block(640), torch.nn.Conv2d(640, 1280, 3, 2, 1), Block(1280)])
        s.u = torch.nn.ModuleList([torch.nn.ConvTranspose2d(1280, 640, 4, 2, 1), Block(640), torch.nn.ConvTranspose2d(640, 320, 4, 2, 1), Block(320)])
        s.out = torch.nn.Conv2d(320, 4, 3, padding=1)
    def forward(s, x):
        x = s.inp(x)
        for l in s.d: x = l(x)
        for l in s.u: x = l(x)
        return s.out(x)
u = UNetish().cuda().half(); xu = torch.randn(2, 4, 64, 64, device="cuda", dtype=torch.half)
def ustep(): u(xu).float().pow(2).mean().backward()
res["unet_like_fp16_bs2_train"] = timed(ustep)
mi = torchvision.models.resnet50().cuda().half().eval(); xi = torch.randn(1, 3, 224, 224, device="cuda", dtype=torch.half)
def istep():
    with torch.no_grad(): mi(xi)
res["resnet50_fp16_bs1_infer"] = timed(istep, n=100)
print("SWEEP_JSON", json.dumps(res), flush=True)
