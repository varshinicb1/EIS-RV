#!/usr/bin/env bash
# Generate a self-signed TLS pair for LOCAL DEVELOPMENT ONLY.
# Output goes to certs/. Both files are gitignored.
# Do NOT use the resulting certificates in any production or shared environment.
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p certs

if [[ -f certs/privkey.pem || -f certs/fullchain.pem ]]; then
    echo "certs/privkey.pem or certs/fullchain.pem already exists. Refusing to overwrite." >&2
    echo "Delete them first if you really want to regenerate." >&2
    exit 1
fi

openssl req -x509 -newkey rsa:4096 -sha256 -nodes \
    -keyout certs/privkey.pem \
    -out certs/fullchain.pem \
    -days 365 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 certs/privkey.pem
chmod 644 certs/fullchain.pem

echo "Generated certs/privkey.pem and certs/fullchain.pem (self-signed, 365 days, localhost)."
echo "These are for local development only. They are gitignored."
