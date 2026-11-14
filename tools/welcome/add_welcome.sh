#!/bin/sh
# Install the first-shell help (tools/welcome/; the release tooling puts it into every build context as rc-welcome/).
# Usage in a Dockerfile:
#   COPY rc-welcome/ /tmp/rc-welcome/
#   RUN sh /tmp/rc-welcome/add_welcome.sh <family> "<image name>" [<README path in the image>] && rm -rf /tmp/rc-welcome
# <family> picks welcome-<family>.txt (quick start; optional "# port=N" / "# hfslow=<command>" lines). A family
# without a file shows the common block only. Changing the help text = editing tools/welcome/welcome-*.txt.
set -eu
D=$(dirname "$0")
fam=$1; name=$2; readme=${3:-}
install -m 644 "$D/rc-welcome.sh" /etc/profile.d/rc-welcome.sh
install -d -m 755 /etc/rc-welcome
for f in "$D"/welcome-*.txt; do install -m 644 "$f" "/etc/rc-welcome/${f##*/welcome-}"; done
printf '%s\n' "$fam" > /etc/rc-image-family
printf '%s\n' "$name" > /etc/rc-image.txt
if [ -n "$readme" ]; then printf '%s\n' "$readme" > /etc/rc-image-readme; else rm -f /etc/rc-image-readme; fi
rm -f /etc/rc-welcome-tunnel.txt /etc/rc-welcome-extra.txt
# rc-tunnel on PATH from the first shell (installs the per-instance binary on first use).
[ -e /usr/local/bin/rc-tunnel ] || install -m 755 "$D/rc-tunnel" /usr/local/bin/rc-tunnel
for rc in /etc/bash.bashrc /etc/bash/bashrc; do
  [ -f "$rc" ] && ! grep -q rc-welcome.sh "$rc" && printf '\n[ -r /etc/profile.d/rc-welcome.sh ] && . /etc/profile.d/rc-welcome.sh\n' >> "$rc"
done
exit 0
