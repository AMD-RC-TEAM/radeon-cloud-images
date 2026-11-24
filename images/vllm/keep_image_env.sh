#!/bin/sh
# Keep the image's toolchain environment (PATH, LD_LIBRARY_PATH, ROCm/Python settings) in SSH sessions.
# Run as the LAST build step, after every ENV.
#
# Why: JupyterLab inherits the image's ENV, but Radeon Cloud's sshd starts each session with sshd's own minimal
# environment. It runs with UsePAM no and PermitUserEnvironment no, and its single SetEnv line carries the proxy
# settings (app/ssh_runtime.py), so /etc/environment and ~/.ssh/environment are not read. Over SSH, python was
# /usr/bin/python (rc-ux, 11-22), and with the right python, torch still failed to load its ROCm libraries.
#
# How: the build-time values are written to /etc/profile.d/zz-rc-image-env.sh. Login shells read it via
# /etc/profile. `ssh host cmd` runs a non-interactive bash, which Ubuntu's bash (built with SSH_SOURCE_BASHRC)
# starts by reading /etc/bash.bashrc, so that file sources the snippet on its first line. List variables get the
# missing entries prepended; other variables are set only when the session has not set them. Only an allowlist
# of toolchain variables is kept, never HF_*, build arguments, or names containing KEY/TOKEN/SECRET/PASSWORD.
set -eu
root=${KEEP_IMAGE_ENV_ROOT:-}   # tests only: write under this directory instead of /
snippet=/etc/profile.d/zz-rc-image-env.sh
LISTS="PATH LD_LIBRARY_PATH LIBRARY_PATH PYTHONPATH CPATH PKG_CONFIG_PATH"
VALUE_RE='^(VIRTUAL_ENV|CONDA_[A-Z0-9_]+|ROCM_[A-Z0-9_]+|HIP_[A-Z0-9_]+|HSA_[A-Z0-9_]+|HCC_[A-Z0-9_]+|MIOPEN_[A-Z0-9_]+|PYTORCH_[A-Z0-9_]+|TORCH_[A-Z0-9_]+|VLLM_[A-Z0-9_]+|SGLANG_[A-Z0-9_]+|AMDGPU_[A-Z0-9_]+|GPU_[A-Z0-9_]+|NCCL_[A-Z0-9_]+|RCCL_[A-Z0-9_]+|LANG|LC_ALL)$'
SECRET_RE='(KEY|TOKEN|SECRET|PASSWORD)'
safe() { case "$1" in *[!A-Za-z0-9/._:+,=@-]*) return 1 ;; esac; return 0; }
mkdir -p "$root/etc/profile.d"
{
  echo "# Written at image build time by keep_image_env.sh: the image's toolchain environment for SSH sessions."
  echo '_rc_add_list() { _rc_n=$1; _rc_v=$2; eval "_rc_cur=\${$_rc_n:-}"; _rc_add=""; _rc_ifs=$IFS; IFS=:'
  echo '  for _rc_d in $_rc_v; do case ":$_rc_cur:" in *":$_rc_d:"*) ;; *) _rc_add="${_rc_add:+$_rc_add:}$_rc_d" ;; esac; done; IFS=$_rc_ifs'
  echo '  if [ -n "$_rc_add" ]; then eval "$_rc_n=\"\$_rc_add\${_rc_cur:+:\$_rc_cur}\""; eval "export $_rc_n"; fi; }'
  for n in $LISTS; do
    eval "v=\${$n:-}"
    [ -n "$v" ] || continue
    safe "$v" || { echo "keep_image_env.sh: unexpected characters in $n" >&2; exit 1; }
    echo "_rc_add_list $n \"$v\""
  done
  env | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' | grep -E "$VALUE_RE" | grep -vE "$SECRET_RE" | sort -u | while read -r n; do
    eval "v=\${$n}"
    safe "$v" || { echo "keep_image_env.sh: skipping $n (unexpected characters)" >&2; continue; }
    echo "[ -n \"\${$n+x}\" ] || export $n=\"$v\""
  done
  echo 'unset -f _rc_add_list; unset _rc_n _rc_v _rc_cur _rc_add _rc_ifs _rc_d'
} > "$root$snippet"
chmod 0644 "$root$snippet"
line="[ -r $snippet ] && . $snippet  # keep_image_env.sh"
rc="$root/etc/bash.bashrc"
if [ -f "$rc" ]; then
    grep -qF "# keep_image_env.sh" "$rc" || { printf '%s\n' "$line" | cat - "$rc" > "$rc.new" && cat "$rc.new" > "$rc" && rm -f "$rc.new"; }
else
    printf '%s\n' "$line" > "$rc"
fi
echo "keep_image_env.sh: SSH sessions keep: $(grep -oE '(_rc_add_list|export) [A-Za-z0-9_]+' "$root$snippet" | awk '{print $2}' | tr '\n' ' ')"
