import os, time, json, numpy as np, torch
r = {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}
r["torch_threads"] = torch.get_num_threads()
a = np.random.rand(2048, 2048); a @ a; t = time.perf_counter()
for _ in range(10): a @ a
r["numpy_mm_gflops"] = round(10 * 2 * 2048**3 / (time.perf_counter() - t) / 1e9)
b = torch.randn(2048, 2048); b @ b; t = time.perf_counter()
for _ in range(10): b @ b
r["torch_cpu_mm_gflops"] = round(10 * 2 * 2048**3 / (time.perf_counter() - t) / 1e9)
x = torch.randn(16, 64, 56, 56); w = torch.randn(64, 64, 3, 3); torch.nn.functional.conv2d(x, w, padding=1); t = time.perf_counter()
for _ in range(5): torch.nn.functional.conv2d(x, w, padding=1)
r["torch_cpu_conv_ms"] = round((time.perf_counter() - t) / 5 * 1000, 1)
class DS(torch.utils.data.Dataset):          # CPU-heavy per-sample work, like decoding/augmentation
    def __len__(self): return 512
    def __getitem__(self, i):
        m = np.random.rand(256, 256); return torch.from_numpy((m @ m).astype(np.float32)[:224, :224]).unsqueeze(0).repeat(3, 1, 1)
dl = torch.utils.data.DataLoader(DS(), batch_size=32, num_workers=8)
t = time.perf_counter(); n = sum(xb.shape[0] for xb in dl); r["dataloader_samples_s"] = round(n / (time.perf_counter() - t))
import torchvision
m = torchvision.models.resnet50().cuda(); opt = torch.optim.SGD(m.parameters(), lr=0.01)
xb = torch.randn(64, 3, 224, 224, device="cuda"); yb = torch.randint(0, 1000, (64,), device="cuda")
def step():
    with torch.autocast("cuda", dtype=torch.bfloat16):
        loss = torch.nn.functional.cross_entropy(m(xb), yb)
    loss.backward(); opt.step(); opt.zero_grad()
for _ in range(10): step()
torch.cuda.synchronize(); t = time.perf_counter()
for _ in range(30): step()
torch.cuda.synchronize(); r["resnet50_bf16_img_s"] = round(30 * 64 / (time.perf_counter() - t))
print("M_JSON", json.dumps(r), flush=True)
