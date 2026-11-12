#!/bin/bash
# Resumably fetch a public Docker Hub image (via the daocloud mirror, which 0004 can reach) into an OCI
# layout and push it to the Wuxi Harbor with the manifest digest preserved.
#   hubfetch.sh <hub-repo> <manifest-digest> <out-dir> <harbor-ref>
# The site edge cuts single connections at ~10 min, so blobs use `curl -C -` with retries, then sha256 checks.
# Works for a single image manifest or an index. crane comes from $CRANE (default: on PATH).
set -u
REPO=$1; DIG=$2; OUT=$3; TARGET=$4
REG=https://docker.m.daocloud.io
CRANE=${CRANE:-crane}
ACC="application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json"
B=$OUT/blobs/sha256; mkdir -p "$B"; cd "$OUT" || exit 1
tok() { curl -s "https://m.daocloud.io/auth/token?service=docker.m.daocloud.io&scope=repository:$REPO:pull" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("token") or d.get("access_token"))'; }
get_manifest() {
  curl -sS -L -H "Authorization: Bearer $(tok)" -H "Accept: $ACC" "$REG/v2/$REPO/manifests/$1" -o "$B/${1#sha256:}" || return 1
  h=$(sha256sum "$B/${1#sha256:}" | cut -d' ' -f1); [ "sha256:$h" = "$1" ] || { echo "MANIFEST MISMATCH $1 got $h"; head -c 300 "$B/${1#sha256:}"; return 1; }
}
get_blob() {
  local d=$1 want=$2 f="$B/${1#sha256:}" got a
  for a in $(seq 1 80); do
    got=$(stat -c%s "$f" 2>/dev/null || echo 0)
    [ "$got" = "$want" ] && return 0
    [ "$got" -gt "$want" ] && rm -f "$f"
    echo "  [$a] ${d:7:12} $got/$want $(date -u +%H:%M:%S)"
    curl -sS -L -C - --max-time 570 -H "Authorization: Bearer $(tok)" -o "$f" "$REG/v2/$REPO/blobs/$d" 2>&1 | tail -1
  done
  echo "FATAL: $d incomplete"; return 1
}
echo "=== $REPO@$DIG $(date -u +%H:%M:%S)"
get_manifest "$DIG" || exit 1
python3 - "$B" "$DIG" > manifests.txt <<'PY' || exit 1
import json,sys,os
b,d=sys.argv[1],sys.argv[2]; m=json.load(open(os.path.join(b,d.split(":")[1])))
print("\n".join(x["digest"] for x in m["manifests"]) if "manifests" in m else "")
PY
while read -r d; do [ -n "$d" ] && { get_manifest "$d" || exit 1; }; done < manifests.txt
python3 - "$B" "$DIG" > blobs.txt <<'PY' || exit 1
import json,sys,os
b,d=sys.argv[1],sys.argv[2]
L=lambda x: json.load(open(os.path.join(b,x.split(":")[1])))
top=L(d); mans=[x["digest"] for x in top["manifests"]] if "manifests" in top else [d]
seen=set()
for md in mans:
    m=L(md)
    for e in [m["config"]]+m.get("layers",[]):
        if e["digest"] not in seen: seen.add(e["digest"]); print(e["digest"], e["size"])
PY
echo "=== $(grep -c . blobs.txt) blobs, $(awk '{s+=$2} END {printf "%.1f", s/2^30}' blobs.txt) GiB"
while read -r d s; do get_blob "$d" "$s" || exit 1; done < blobs.txt
echo "=== verify $(date -u +%H:%M:%S)"
while read -r d s; do h=$(sha256sum "$B/${d#sha256:}" | cut -d' ' -f1); [ "$h" = "${d#sha256:}" ] || { echo "MISMATCH $d"; exit 1; }; done < blobs.txt
MT=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("mediaType",""))' "$B/${DIG#sha256:}")
printf '{"imageLayoutVersion":"1.0.0"}' > oci-layout
printf '{"schemaVersion":2,"mediaType":"application/vnd.oci.image.index.v1+json","manifests":[{"mediaType":"%s","digest":"%s","size":%s}]}' "$MT" "$DIG" "$(stat -c%s "$B/${DIG#sha256:}")" > index.json
echo "=== push $(date -u +%H:%M:%S) -> $TARGET"
GODEBUG=http2client=0 "$CRANE" push --insecure "$OUT" "$TARGET" 2>&1 | tail -3
echo "=== DONE $(date -u +%H:%M:%S)"
