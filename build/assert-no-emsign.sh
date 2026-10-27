#!/bin/sh
# Build-time check for base images: fail if the system CA bundle still contains a root flagged in the 2026-10
# emSign incident (matched by SHA-256 fingerprint, never by name), or looks too small to be a real bundle.
# Needs openssl and awk.  Installed as /bin/assert-no-emsign; add new fingerprints to FLAGGED when they are verified.
FLAGGED="86A1ECBA089C4A8D3BBE2734C612BA341D813E043CF9E8A862CD5C57A36BBE6B D7A7A0FB5D7E2731D771E9484EBCDEF71D5F0C3E0A2948782BC83EE0EA699EF4"
BUNDLE=${1:-/etc/ssl/certs/ca-certificates.crt}
T=$(mktemp -d) || exit 1
trap 'rm -rf "$T"' EXIT
awk -v d="$T" '/-----BEGIN CERTIFICATE-----/{n++; f=sprintf("%s/c%04d.pem", d, n)} f{print > f}' "$BUNDLE"
count=0; bad=0
for c in "$T"/c*.pem; do
  [ -e "$c" ] || break
  count=$((count + 1))
  fp=$(openssl x509 -in "$c" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2 | tr -d :)
  for f in $FLAGGED; do
    if [ "$fp" = "$f" ]; then echo "assert-no-emsign: FLAGGED root $fp present in $BUNDLE" >&2; bad=1; fi
  done
done
if [ "$count" -lt 100 ]; then echo "assert-no-emsign: only $count certificates in $BUNDLE" >&2; exit 1; fi
[ "$bad" = 0 ] && echo "assert-no-emsign: $count certificates, none flagged"
exit $bad
