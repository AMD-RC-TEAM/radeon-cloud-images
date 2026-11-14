# Radeon Cloud first-shell help. Renders /etc/rc-welcome/<family>.txt + /etc/rc-welcome/common.txt (tools/welcome/
# welcome-*.txt in radeon-cloud-images); add_welcome.sh installs them. Family: /etc/rc-image-family; name: /etc/rc-image.txt.
# Editing the help = editing those text files. Placeholders: {B} bold, {D} dim, {R} reset, {PORT}, {README}, {HFSLOW}.
# A family file may start with "# port=N" and "# hfslow=<command>" lines. No family file -> common only.
# Printed once per home, first interactive bash. Silent for bash -c/scripts, ~/.rc-welcome-shown|hidden, RC_WELCOME=0.
# Preview: RC_WELCOME_FORCE=1 bash -ic true
case $- in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac
[ -n "${RC_WELCOME_DONE:-}" ] && return 0
RC_WELCOME_DONE=1
[ "${RC_WELCOME:-1}" = 0 ] && return 0
if [ -z "${RC_WELCOME_FORCE:-}" ]; then
  [ -n "${HOME:-}" ] && [ -w "$HOME" ] || return 0
  { [ -e "$HOME/.rc-welcome-shown" ] || [ -e "$HOME/.rc-welcome-hidden" ]; } && return 0
  : > "$HOME/.rc-welcome-shown" 2>/dev/null || return 0
fi
__rcw() {
  local dir=${RC_WELCOME_DIR:-/etc/rc-welcome} B='' D='' R='' fam name py n=0 id gpu v_rocm vers port=7860 hfslow='pip install modelscope; modelscope download --model <id>' readme='' r d x
  if { [ -t 1 ] || [ -n "${RC_WELCOME_COLOR:-}" ]; } && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != dumb ]; then
    B=$'\e[1m'; D=$'\e[2m'; R=$'\e[0m'
  fi
  fam=${RC_WELCOME_FAMILY:-$(cat /etc/rc-image-family 2>/dev/null)}
  name=${RC_WELCOME_NAME:-$(head -n1 /etc/rc-image.txt 2>/dev/null)}; name=${name:-Radeon Cloud instance}
  for r in /dev/dri/renderD*; do
    [ -e "$r" ] || continue; d=/sys/class/drm/${r##*/}/device
    [ -r "$d/vendor" ] && [ "$(cat "$d/vendor")" = 0x1002 ] || continue
    n=$((n+1)); id=$(cat "$d/device" 2>/dev/null)
  done
  case "$id" in 0x744b) gpu='Radeon PRO W7900D (48 GB)';; 0x7448) gpu='Radeon PRO W7900 (48 GB)';; 0x7551) gpu='Radeon AI PRO R9700 (32 GB)';; *) gpu='AMD Radeon GPU';; esac
  v_rocm=$(cut -d- -f1 /opt/rocm/.info/version 2>/dev/null)
  if [ -z "$v_rocm" ]; then for x in /opt/rocm-[0-9]*; do [ -d "$x" ] && v_rocm=${x#/opt/rocm-}; done; fi
  vers=${v_rocm:+ROCm $v_rocm}
  py=$(command -v python3 || command -v python)
  [ -n "$py" ] && vers="$vers$(timeout 2 "$py" - 2>/dev/null <<'PY'
from importlib import metadata as m
out = []
for pkg, label in (("torch", "PyTorch"), ("vllm", "vLLM"), ("sglang", "SGLang"), ("comfyui", "ComfyUI")):
    try: out.append(f"{label} {m.version(pkg).split('+')[0]}")
    except Exception: pass
print("".join(" · " + s for s in out), end="")
PY
)"
  vers=${vers# · }
  x=$(head -n1 /etc/rc-image-readme 2>/dev/null); [ -z "$x" ] && [ -n "$fam" ] && x=/opt/$fam/README.md
  [ -n "$x" ] && [ -r "$x" ] && readme=$'\n'"  This image: $x"
  printf '%s%s%s\n' "$B" "$name" "$R"
  [ -n "$vers" ] && printf '%s\n' "$vers"
  [ "$n" -gt 0 ] && printf '%s GPU%s: %s\n' "$n" "$([ "$n" -gt 1 ] && echo s)" "$gpu"
  echo
  __rcw_render() {
    local line
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in '# '*=*) continue;; esac
      # Quoted replacements: bash 5.2 would otherwise expand '&' in the values.
      line=${line//\{B\}/"$B"}; line=${line//\{D\}/"$D"}; line=${line//\{R\}/"$R"}
      line=${line//\{PORT\}/"$port"}; line=${line//\{README\}/"$readme"}; line=${line//\{HFSLOW\}/"$hfslow"}
      printf '%s\n' "$line"
    done < "$1"
  }
  if [ -n "$fam" ] && [ -r "$dir/$fam.txt" ]; then
    x=$(sed -n 's/^# port=\([0-9]*\).*/\1/p' "$dir/$fam.txt" | head -1); port=${x:-7860}
    x=$(sed -n 's/^# hfslow=//p' "$dir/$fam.txt" | head -1); [ -n "$x" ] && hfslow=$x
    __rcw_render "$dir/$fam.txt"; echo
  fi
  [ -r "$dir/common.txt" ] && __rcw_render "$dir/common.txt"
  unset -f __rcw_render
}
__rcw 2>/dev/null
unset -f __rcw
