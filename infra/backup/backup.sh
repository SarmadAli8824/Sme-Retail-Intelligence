#!/usr/bin/env sh
set -eu
: "${DATABASE_URL:?DATABASE_URL is required}"; : "${GPG_PASSPHRASE:?GPG_PASSPHRASE is required}"; : "${OCI_UPLOAD_URL:?OCI_UPLOAD_URL pre-authenticated request URL is required}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
pg_dump "$DATABASE_URL" | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$GPG_PASSPHRASE" > "/tmp/retail-${stamp}.sql.gpg"
curl --fail --upload-file "/tmp/retail-${stamp}.sql.gpg" "${OCI_UPLOAD_URL}/retail-${stamp}.sql.gpg"
rm -f "/tmp/retail-${stamp}.sql.gpg"

