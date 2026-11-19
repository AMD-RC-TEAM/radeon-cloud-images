#!/bin/sh
# Bake openssh-server into the image so Radeon Cloud's SSH setup does not apt-install it at launch.
# The platform skips its install step when sshd is already present (app/ssh_runtime.py), so SSH no longer
# depends on reaching the Ubuntu archive from the cluster at launch time (it timed out at the China evening peak).
# Host keys are never baked: the platform generates them per instance at runtime.
set -eu
if command -v sshd >/dev/null 2>&1 || [ -x /usr/sbin/sshd ]; then
    echo "openssh-server already present"; exit 0
fi
. /etc/os-release
case "${ID:-} ${ID_LIKE:-}" in
    *ubuntu*|*debian*) ;;
    *) echo "add_openssh.sh: unsupported base OS ${ID:-unknown}" >&2; exit 1 ;;
esac
src=/etc/apt/sources.list
[ -r /etc/apt/sources.list.d/ubuntu.sources ] && src=/etc/apt/sources.list.d/ubuntu.sources
[ -r /etc/apt/sources.list.d/debian.sources ] && src=/etc/apt/sources.list.d/debian.sources
# Keep the file name: apt parses deb822 (*.sources) and one-line (*.list) formats by extension.
tmpd=$(mktemp -d)
tmp="$tmpd/$(basename "$src")"
cp "$src" "$tmp"
# APT_MIRROR (build arg): a mirror reachable from the build cluster. Only the distribution source is used, so
# third-party repositories in the base image are neither needed nor contacted.
if [ -n "${APT_MIRROR:-}" ]; then
    sed -i -e "s@//[a-z.]*archive.ubuntu.com@//${APT_MIRROR}@g" -e "s@//security.ubuntu.com@//${APT_MIRROR}@g" \
        -e "s@//deb.debian.org@//${APT_MIRROR}@g" "$tmp"
fi
created_policy=0
if [ ! -e /usr/sbin/policy-rc.d ]; then
    printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod 755 /usr/sbin/policy-rc.d && created_policy=1
fi
export DEBIAN_FRONTEND=noninteractive
opts="-o Dir::Etc::sourcelist=$tmp -o Dir::Etc::sourceparts=-"
apt-get $opts update
apt-get $opts install -y --no-install-recommends openssh-server
rm -rf /var/lib/apt/lists/* "$tmpd"
[ "$created_policy" = 1 ] && rm -f /usr/sbin/policy-rc.d
rm -f /etc/ssh/ssh_host_*
command -v sshd >/dev/null 2>&1 || [ -x /usr/sbin/sshd ]
echo "openssh-server installed: $( (dpkg-query -W -f='${Version}' openssh-server) 2>/dev/null)"
