#!/usr/bin/env bash
# Backup this app ONLY. Online by default; no service is stopped by this script.
# Stop only dj-nazyer first when an exactly consistent DB/media pair is required.
set -euo pipefail
umask 077
: "${NAZYER_MYSQL_CREDENTIALS:?Set an absolute path to a private MySQL client option file}"
: "${NAZYER_BACKUP_DIR:?Set an absolute backup output directory}"
NAZYER_MEDIA_PARENT=${NAZYER_MEDIA_PARENT:-/var/lib/dj-nazyer}
[[ "$NAZYER_MYSQL_CREDENTIALS" = /* && "$NAZYER_BACKUP_DIR" = /* && "$NAZYER_MEDIA_PARENT" = /* ]] || exit 1
[[ -f "$NAZYER_MYSQL_CREDENTIALS" && -r "$NAZYER_MYSQL_CREDENTIALS" ]] || exit 1
[[ "$(stat -c %a -- "$NAZYER_MYSQL_CREDENTIALS")" = 600 ]] || {
    printf 'MySQL client option file must have mode 0600.\n' >&2
    exit 1
}
[[ -d "$NAZYER_MEDIA_PARENT/uploads" ]] || exit 1
mkdir -p "$NAZYER_BACKUP_DIR"
exec 9>"$NAZYER_BACKUP_DIR/.backup.lock"
flock -n 9 || {
    printf 'Another DJ NAZYER backup is running.\n' >&2
    exit 1
}
nazyer_stamp=$(date -u +%Y%m%dT%H%M%SZ)
nazyer_temp=$(mktemp -d "$NAZYER_BACKUP_DIR/.nazyer-backup-XXXXXX")
trap 'rm -rf -- "$nazyer_temp"' EXIT
mysqldump --defaults-extra-file="$NAZYER_MYSQL_CREDENTIALS" \
  --single-transaction --quick --no-tablespaces --set-gtid-purged=OFF \
  --skip-triggers --skip-routines --skip-events \
  dj_nazyer | gzip > "$nazyer_temp/dj_nazyer.sql.gz"
tar --exclude='uploads/.processing.lock' -czf "$nazyer_temp/media.tar.gz" \
  -C "$NAZYER_MEDIA_PARENT" uploads
tar -czf "$nazyer_temp/bundle.tar.gz" \
  -C "$nazyer_temp" dj_nazyer.sql.gz media.tar.gz
# Atomic publication in the same filesystem; never overwrite an existing backup.
ln "$nazyer_temp/bundle.tar.gz" "$NAZYER_BACKUP_DIR/dj-nazyer-$nazyer_stamp.tar.gz"
printf 'Backup created: %s\n' "$NAZYER_BACKUP_DIR/dj-nazyer-$nazyer_stamp.tar.gz"
# Prune only valid, regular backup bundles, and only AFTER successful publication.
# UTC timestamp names sort chronologically; retain the most recent 14 bundles.
mapfile -t nazyer_backups < <(
    find "$NAZYER_BACKUP_DIR" -maxdepth 1 -regextype posix-extended -type f \
      -regex '.*/dj-nazyer-[0-9]{8}T[0-9]{6}Z\.tar\.gz' -printf '%f\n' | LC_ALL=C sort -r
)
for nazyer_old in "${nazyer_backups[@]:14}"; do
    rm -- "$NAZYER_BACKUP_DIR/$nazyer_old"
done
