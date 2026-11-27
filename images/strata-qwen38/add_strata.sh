#!/bin/sh
# Install the Strata engine bundle (radeon-engine4's B0 serving bundle) from /tmp/strata/context.tgz.
# The bundle comes from a sha-pinned Harbor image (see the Dockerfile) and is checked again here against $STRATA_BUNDLE_SHA256.
# Engine server: /opt/strata/control with its own venv (/opt/strata/venv, from the bundle's requirements.lock);
# serving scripts and binaries: /opt/b0/<version>, with /opt/b0/current pointing at it.
set -eu
: "${STRATA_BUNDLE_SHA256:?}" "${STRATA_BUNDLE_VERSION:?}"
cd /tmp/strata
echo "${STRATA_BUNDLE_SHA256}  context.tgz" | sha256sum -c -
mkdir -p ctx && tar -xzf context.tgz -C ctx
test -d "ctx/b0/${STRATA_BUNDLE_VERSION}" || { echo "bundle has no b0/${STRATA_BUNDLE_VERSION}" >&2; exit 1; }
mkdir -p /opt/strata /opt/b0
cp -r ctx/control /opt/strata/control
cp -r "ctx/b0/${STRATA_BUNDLE_VERSION}" "/opt/b0/${STRATA_BUNDLE_VERSION}"
ln -sfn "/opt/b0/${STRATA_BUNDLE_VERSION}" /opt/b0/current
cp ctx/requirements.lock /opt/strata/requirements.lock
chmod 0755 /opt/b0/current/run.sh /opt/b0/current/b0_serve.py /opt/b0/current/bin/strata /opt/b0/current/bin/strata-numa
python3 -m venv /opt/strata/venv
/opt/strata/venv/bin/pip install --no-cache-dir -r /opt/strata/requirements.lock
# The engine binary must find every ROCm library in this image.
! ldd /opt/b0/current/bin/strata | grep "not found"
cd / && rm -rf /tmp/strata
echo "add_strata.sh: bundle ${STRATA_BUNDLE_VERSION} installed"
