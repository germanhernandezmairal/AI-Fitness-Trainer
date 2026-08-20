#!/usr/bin/env bash
set -euo pipefail

# Nightly Postgres backup: dumps the `db` service (from deploy/docker-compose.prod.yml), gzips it,
# and uploads it to Oracle Object Storage. Run via cron on the VM — see deploy/README.md for the
# crontab line. Requires: this script's directory contains docker-compose.prod.yml and .env
# (loaded automatically by `docker compose`), and the `oci` CLI is installed and configured
# (`oci setup config`) with access to the free-tier Object Storage bucket named in
# OCI_BACKUP_BUCKET below.

cd "$(dirname "$0")"

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
DUMP_FILE="/tmp/fitness-backup-${TIMESTAMP}.sql.gz"
OCI_BACKUP_BUCKET="${OCI_BACKUP_BUCKET:?Set OCI_BACKUP_BUCKET in the environment or crontab line}"

# Source POSTGRES_* from deploy/.env so this script works standalone (not only via `docker compose`).
set -a
# shellcheck disable=SC1091
source .env
set +a

docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${DUMP_FILE}"

oci os object put \
  --bucket-name "${OCI_BACKUP_BUCKET}" \
  --file "${DUMP_FILE}" \
  --name "postgres/$(basename "${DUMP_FILE}")"

rm -f "${DUMP_FILE}"

echo "Backup complete: postgres/$(basename "${DUMP_FILE}") uploaded to ${OCI_BACKUP_BUCKET}"
