# Radeon Cloud first-shell tips: printed once, in the first interactive bash of a fresh home directory.
# Silent for non-interactive shells (bash -c, scripts), when ~/.rc-welcome-shown or ~/.rc-welcome-hidden exists,
# or when RC_WELCOME=0. Sourced from /etc/profile.d (login shells) and /etc/bash.bashrc (Jupyter terminals).
case $- in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac
[ -n "${RC_WELCOME_DONE:-}" ] && return 0
RC_WELCOME_DONE=1
[ "${RC_WELCOME:-1}" = 0 ] && return 0
[ -n "${HOME:-}" ] && [ -w "$HOME" ] || return 0
[ -e "$HOME/.rc-welcome-shown" ] || [ -e "$HOME/.rc-welcome-hidden" ] && return 0
: > "$HOME/.rc-welcome-shown" 2>/dev/null || return 0
{
  printf 'Radeon Cloud: %s\n' "$(head -n1 /etc/rc-image.txt 2>/dev/null || echo 'GPU instance (Radeon PRO W7900D)')"
  [ -r /etc/rc-welcome-tunnel.txt ] && cat /etc/rc-welcome-tunnel.txt
  [ -r /etc/rc-image-readme.txt ] && cat /etc/rc-image-readme.txt
  [ -r /etc/rc-welcome-extra.txt ] && cat /etc/rc-welcome-extra.txt
  printf 'Hide this message: touch ~/.rc-welcome-hidden\n'
} 2>/dev/null
