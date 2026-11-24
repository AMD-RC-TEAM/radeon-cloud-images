set -u
echo "sshd processes before: $(pgrep -a sshd | tr '\n' ';')"
PROBE='import os,time,torch; n=4096; a=torch.randn(n,n,device="cuda"); b=torch.randn(n,n,device="cuda"); a@b; torch.cuda.synchronize(); t=time.perf_counter()
for _ in range(20): a@b
torch.cuda.synchronize(); print("env=%s blas=%s fp32_4096=%.1f TFLOPS" % (os.environ.get("TORCH_BLAS_PREFER_HIPBLASLT"), torch.backends.cuda.preferred_blas_library(), 2*n**3*20/(time.perf_counter()-t)/1e12))'
d=$(mktemp -d); k=$d/k; ssh-keygen -q -t ed25519 -N "" -f $k; ssh-keygen -q -t ed25519 -N "" -f $d/hostkey
mkdir -p /run/sshd; /usr/sbin/sshd -E $d/log -p 2222 -h $d/hostkey -o PidFile=$d/pid -o AuthorizedKeysFile=$k.pub -o PermitRootLogin=prohibit-password -o StrictModes=no
sleep 1; echo "sshd log: $(tail -3 $d/log 2>/dev/null | tr "\n" ";")"; /usr/sbin/sshd -t -h $d/hostkey 2>&1 | tail -2
ssh -n -i $k -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=VERBOSE root@127.0.0.1 \
  "echo user=\$(id -un) python=\$(command -v python3) env_var=\${TORCH_BLAS_PREFER_HIPBLASLT-unset}; python3 -c '$PROBE'" > $d/sshout 2>&1; echo "ssh exit=$?"; grep -v Warning $d/sshout | tail -4
echo "--- ssh client:"; grep -v Warning $d/sshout | tail -6; echo "--- sshd log:"; tail -8 $d/log; kill $(cat $d/pid) 2>/dev/null; sleep 1; rm -rf $d
echo "sshd processes after: $(pgrep -a sshd | tr '\n' ';')"
