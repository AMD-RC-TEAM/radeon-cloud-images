# 50-step HF Trainer fine-tune on a random-init GPT-2-small-shaped model with synthetic data (no downloads).
import torch, time, json, os, sys, transformers
from transformers import GPT2Config, GPT2LMHeadModel, Trainer, TrainingArguments
prec = sys.argv[1]  # fp32 | bf16
torch.manual_seed(0)
cfg = GPT2Config(n_layer=12, n_embd=768, n_head=12, n_positions=512, vocab_size=50257)
model = GPT2LMHeadModel(cfg)
class DS(torch.utils.data.Dataset):
    def __len__(self): return 4096
    def __getitem__(self, i):
        g = torch.Generator().manual_seed(i); ids = torch.randint(0, 50257, (512,), generator=g)
        return {"input_ids": ids, "labels": ids}
args = TrainingArguments(output_dir="/tmp/hfout", per_device_train_batch_size=8, max_steps=60, logging_steps=1000,
                         save_strategy="no", report_to=[], bf16=(prec=="bf16"), learning_rate=5e-5, disable_tqdm=True)
class T(Trainer): pass
times = []
from transformers import TrainerCallback
class CB(TrainerCallback):
    def on_step_begin(self, *a, **k): torch.cuda.synchronize(); self.t = time.perf_counter()
    def on_step_end(self, *a, **k): torch.cuda.synchronize(); times.append(time.perf_counter()-self.t)
tr = Trainer(model=model, args=args, train_dataset=DS(), callbacks=[CB()])
t0 = time.perf_counter(); tr.train(); wall = time.perf_counter()-t0
s = sorted(times[10:])
print("HF_JSON", json.dumps({"prec": prec, "transformers": transformers.__version__, "blas": str(torch.backends.cuda.preferred_blas_library()),
      "env_blas": os.environ.get("TORCH_BLAS_PREFER_HIPBLASLT"), "attn": model.config._attn_implementation,
      "median_step_ms": round(1000*s[len(s)//2],1), "wall_60_steps_s": round(wall,1)}), flush=True)
