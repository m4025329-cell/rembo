#!/usr/bin/env bash
# =====================================================================
#  BlackLotusVPN — зашифрованный бэкап SQLite-БД + audit-логов.
#
#  Как работает:
#   1. Дампит SQLite (safe .backup) во временный файл.
#   2. tar-архивит db-dump + logs/audit.log.
#   3. Шифрует всё GPG в файл вида backups/blacklotus-<ts>.tar.gz.gpg
#      для получателя BACKUP_GPG_RECIPIENT.
#   4. Если задан BACKUP_REMOTE — заливает через rsync.
#
#  Крон-пример (ежедневно 03:15):
#     15 3 * * *  /opt/blacklotus/scripts/backup.sh >>/var/log/blacklotus-backup.log 2>&1
# =====================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# Читаем .env
if [[ -f .env ]]; then
    set -a; source .env; set +a
fi

: "${DATABASE_URL:?DATABASE_URL не задан}"
: "${BACKUP_GPG_RECIPIENT:?BACKUP_GPG_RECIPIENT не задан (email/keyid GPG)}"

TS=$(date -u +%Y%m%d-%H%M%S)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

mkdir -p backups

# ── 1. Дамп SQLite (или другого движка) ────────────────────────────
if [[ "$DATABASE_URL" == sqlite:///* ]]; then
    DBFILE="${DATABASE_URL#sqlite:///}"
    if [[ ! -f "$DBFILE" ]]; then
        echo "БД не найдена: $DBFILE"; exit 1
    fi
    sqlite3 "$DBFILE" ".backup '$WORK/blacklotus.db'"
    chmod 600 "$WORK/blacklotus.db"
else
    echo "Only SQLite поддержан этим скриптом. Для PG — pg_dump." >&2
    exit 2
fi

# ── 2. Собираем аудит и app-логи ───────────────────────────────────
mkdir -p "$WORK/logs"
[[ -f logs/audit.log ]] && cp logs/audit.log "$WORK/logs/"
[[ -f logs/app.log   ]] && cp logs/app.log   "$WORK/logs/"

# ── 3. Архив + GPG ─────────────────────────────────────────────────
ARCHIVE="backups/blacklotus-$TS.tar.gz"
tar -C "$WORK" -czf "$ARCHIVE" .
chmod 600 "$ARCHIVE"

gpg --batch --yes --trust-model always \
    --recipient "$BACKUP_GPG_RECIPIENT" \
    --output "$ARCHIVE.gpg" --encrypt "$ARCHIVE"

# Незашифрованный tar удаляем сразу
shred -u "$ARCHIVE" 2>/dev/null || rm -f "$ARCHIVE"

echo "✅ Бэкап: $ARCHIVE.gpg"

# ── 4. Заливка на удалённый сервер (опционально) ───────────────────
if [[ -n "${BACKUP_REMOTE:-}" ]]; then
    rsync -av --chmod=600 "$ARCHIVE.gpg" "$BACKUP_REMOTE/"
    echo "📤 Загружено на $BACKUP_REMOTE"
fi

# ── 5. Чистим старые бэкапы (>14 дней) ─────────────────────────────
find backups -name 'blacklotus-*.tar.gz.gpg' -mtime +14 -delete || true
