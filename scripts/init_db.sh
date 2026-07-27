#!/usr/bin/env bash
# Applies all migrations in db/migrations, in order, against $DATABASE_URL.
set -euo pipefail

: "${DATABASE_URL:?Set DATABASE_URL, e.g. postgresql://localhost/musicrec}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="$SCRIPT_DIR/../db/migrations"

for f in "$MIGRATIONS_DIR"/*.sql; do
    echo "Applying $f"
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
