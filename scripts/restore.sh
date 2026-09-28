#!/usr/bin/env bash
# Восстановить БД из зашифрованного бэкапа.
# Использование: bash scripts/restore.sh backups/blacklotus-<ts>.tar.gz.gpg
set -euo pipefail

ARCH="${1:?путь к .gpg-архиву обязателен}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
set -a; source .env; set +a

: "${DATABASE_URL:?DATABASE_URL не задан}"
DBFILE="${DATABASE_URL#sqlite:///}"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

gpg --decrypt --output "$WORK/dump.tar.gz" "$ARCH"
tar -xzf "$WORK/dump.tar.gz" -C "$WORK"
[[ -f "$WORK/blacklotus.db" ]] || { echo "Нет blacklotus.db в архиве"; exit 1; }

echo "Текущая БД будет заменена: $DBFILE"
read -r -p "Продолжить? (yes/no) " ans
[[ "$ans" == "yes" ]] || exit 0

install -m 600 "$WORK/blacklotus.db" "$DBFILE"
echo "✅ БД восстановлена."
