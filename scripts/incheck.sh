# Runs inside the launched instance (kubectl exec -i ... bash -s). Throwaway instance; deleted afterwards.
set -u
PROBE='import os,time,torch; n=4096; a=torch.randn(n,n,device="cuda"); b=torch.randn(n,n,device="cuda"); a@b; torch.cuda.synchronize(); t=time.perf_counter()
for _ in range(20): a@b
torch.cuda.synchronize(); print("env=%s blas=%s fp32_4096=%.1f TFLOPS" % (os.environ.get("TORCH_BLAS_PREFER_HIPBLASLT"), torch.backends.cuda.preferred_blas_library(), 2*n**3*20/(time.perf_counter()-t)/1e12))'
echo "== 0. plain python in the container"
python3 -c "$PROBE" 2>&1 | tail -1
echo "== A. jupyter server process env"
for p in $(pgrep -f "jupyter-lab|jupyter lab|jupyter-server|jupyter_server" | head -3); do echo "pid $p: $(tr '\0' '\n' < /proc/$p/environ | grep -E '^TORCH_BLAS_PREFER_HIPBLASLT=' || echo 'TORCH_BLAS_PREFER_HIPBLASLT unset')"; done
echo "== B. real kernel via nbconvert"
d=$(mktemp -d); python3 - "$d/t.ipynb" "$PROBE" <<'PY'
import json, sys
json.dump({"cells": [{"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": sys.argv[2]}],
           "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}, "nbformat": 4, "nbformat_minor": 5}, open(sys.argv[1], "w"))
PY
jupyter nbconvert --to notebook --execute "$d/t.ipynb" --output out.ipynb >/dev/null 2>&1 && python3 -c "import json,sys;nb=json.load(open(sys.argv[1]));print(''.join((lambda t: ''.join(t) if isinstance(t, list) else t)(o.get('text','')) for o in nb['cells'][0]['outputs']).strip())" "$d/out.ipynb" || echo "nbconvert failed"
echo "== C. real SSH session to localhost"
k=$(mktemp -d)/k; ssh-keygen -q -t ed25519 -N "" -f $k; mkdir -p ~/.ssh; cat $k.pub >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys
port=22; pgrep -x sshd >/dev/null || { ssh-keygen -A >/dev/null 2>&1; mkdir -p /run/sshd; /usr/sbin/sshd -p 2222; port=2222; echo "(started temporary sshd on 2222)"; }
ssh -i $k -p $port -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1 "echo login-shell:\$0 user:\$(id -un); command -v python3; python3 -c '$PROBE'" 2>&1 | grep -v Warning | tail -4
sed -i "\|$(cut -d' ' -f2 $k.pub)|d" ~/.ssh/authorized_keys; [ $port = 2222 ] && pkill -f "sshd -p 2222"
echo "== D. overrides"; pgrep -f "sshd -p 2222" >/dev/null && echo "WARN temp sshd still running" || echo "temp sshd stopped"; grep -c . ~/.ssh/authorized_keys 2>/dev/null
TORCH_BLAS_PREFER_HIPBLASLT=1 python3 -c "$PROBE" 2>&1 | tail -1
python3 -c 'import torch; torch.backends.cuda.preferred_blas_library("cublaslt"); print("after preferred_blas_library(cublaslt):", torch.backends.cuda.preferred_blas_library())' 2>&1 | tail -1
echo "== E. image"; cat /etc/profile.d/zz-rc-image-env.sh 2>/dev/null | grep -c TORCH_BLAS; python3 -c 'import torch;print(torch.__version__)'
