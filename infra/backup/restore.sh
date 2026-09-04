#!/usr/bin/env sh
set -eu
: "${DATABASE_URL:?DATABASE_URL is required}"
: "${GPG_PASSPHRASE:?GPG_PASSPHRASE is required}"
: "${SOURCE_GPG_FILE:?SOURCE_GPG_FILE is required}"
test -f "$SOURCE_GPG_FILE"
gpg --batch --quiet --decrypt --passphrase "$GPG_PASSPHRASE" "$SOURCE_GPG_FILE" | psql "$DATABASE_URL" --set ON_ERROR_STOP=on
