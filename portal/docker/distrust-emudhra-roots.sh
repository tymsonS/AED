#!/bin/sh
# Workaround for the eMudhra emSign CA security incident (OTD-3344):
# https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576
# https://bugs.debian.org/1151413
#
# Distrusts (same as Debian ca-certificates 20250419+deb13u1):
#  - "emSign ECC Root CA - G3" - root of the compromised intermediates (removed in certifi 2026.10.19),
#  - "AAA Certificate Services" (Sectigo/Comodo) - cross-signed the compromised eMudhra intermediates
#    (e.g. "EM EV TLS CA - G3A-1", valid until 2028), so chains via AAA bypass the G3 removal.
#    The cross-certs are revoked, but OpenSSL clients (curl, requests, pip) don't check CRLs.
# in:
#  - the Debian system trust store (bullseye ca-certificates has no fix),
#  - every CA bundle in Python site-packages, incl. certifi copies vendored by pip and pipenv.
#    pip >= 26.2.2 (which drops G3) requires Python >= 3.10, so it has to be patched here.
#
# Idempotent - run again after every step that installs Python packages.
set -eu

for crt in mozilla/emSign_ECC_Root_CA_-_G3.crt mozilla/Comodo_AAA_Services_root.crt; do
    sed -i "s|^$crt\$|!$crt|" /etc/ca-certificates.conf
done
update-ca-certificates --fresh > /dev/null

python - <<'EOF'
import base64, glob, hashlib, os, re, site, sys, sysconfig

DISTRUSTED = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b": "emSign ECC Root CA - G3",
    "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4": "AAA Certificate Services",
}
cert_re = re.compile(
    r"\n?(?:#[^\n]*\n)*-----BEGIN CERTIFICATE-----\n(.*?)-----END CERTIFICATE-----\n?",
    re.S,
)


def distrusted(match):
    try:
        der = base64.b64decode("".join(match.group(1).split()), validate=True)
    except ValueError:  # malformed certs, e.g. in packages' test fixtures
        return None
    return DISTRUSTED.get(hashlib.sha256(der).hexdigest())


dirs = {sysconfig.get_paths()[k] for k in ("purelib", "platlib")} | set(site.getsitepackages())
bundles = {p for d in dirs for p in glob.glob(os.path.join(d, "**", "*.pem"), recursive=True)}
bundles.add("/etc/ssl/certs/ca-certificates.crt")

still_trusted = []
for path in sorted(bundles):
    with open(path, encoding="latin-1") as f:
        text = f.read()
    names = [n for n in map(distrusted, cert_re.finditer(text)) if n]
    if not names:
        continue
    if path.startswith("/etc/"):
        still_trusted.append(f"{path} ({', '.join(names)})")
        continue
    with open(path, "w", encoding="latin-1") as f:
        f.write(cert_re.sub(lambda m: "" if distrusted(m) else m.group(0), text))
    print(f"Removed {', '.join(names)} from {path}")

if still_trusted:
    sys.exit("Distrusted CAs still present in: " + "; ".join(still_trusted))
EOF
