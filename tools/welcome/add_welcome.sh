#!/bin/sh
# Install the first-shell tips (tools/welcome/rc-welcome.sh). The release tooling puts tools/welcome/ into every
# build context as rc-welcome/. Usage in a Dockerfile:
#   COPY rc-welcome/ /tmp/rc-welcome/
#   RUN sh /tmp/rc-welcome/add_welcome.sh "<one-line description>" [<README path in the image>] && rm -rf /tmp/rc-welcome
set -eu
D=$(dirname "$0")
install -m 644 "$D/rc-welcome.sh" /etc/profile.d/rc-welcome.sh
printf '%s\n' "$1" > /etc/rc-image.txt
install -m 644 "$D/rc-welcome-tunnel.txt" /etc/rc-welcome-tunnel.txt
if [ -n "${2:-}" ]; then printf 'This image: %s\n' "$2" > /etc/rc-image-readme.txt; else rm -f /etc/rc-image-readme.txt; fi
for rc in /etc/bash.bashrc /etc/bash/bashrc; do
  [ -f "$rc" ] && ! grep -q rc-welcome.sh "$rc" && printf '\n[ -r /etc/profile.d/rc-welcome.sh ] && . /etc/profile.d/rc-welcome.sh\n' >> "$rc"
done
exit 0
