# 💾 Бэкапы BlackLotusVPN

Все бэкапы шифруются GPG. Незашифрованные архивы не хранятся.

## Что бэкапится

- `db-data/blacklotus.db` — вся БД (юзеры, подписки, ключи, поддержка).
- `logs/audit.log`, `logs/app.log` — журнал действий.
- `/etc/blacklotus/ports.env` — выбранные порты (на VPS).
- Конфиг 3x-ui (`/etc/x-ui/x-ui.db`) — на VPS через отдельный tar.

## Настройка

1. Сгенерируй GPG-ключ (лучше на отдельной машине или yubikey):

   ```bash
   gpg --full-generate-key
   gpg --list-keys
   gpg --export --armor <keyid> > backup-pub.asc
   ```

2. На сервере импортируй **только публичный** ключ:

   ```bash
   gpg --import backup-pub.asc
   gpg --edit-key <keyid>   # trust → 5 → save
   ```

3. Пропиши в `.env`:

   ```
   BACKUP_GPG_RECIPIENT=<keyid или email>
   BACKUP_REMOTE=user@backup-host:/srv/backups/blacklotus
   ```

4. Проверь:

   ```bash
   bash scripts/backup.sh
   ls -la backups/
   ```

5. Крон:

   ```
   15 3 * * *  cd /opt/blacklotus && bash scripts/backup.sh >>/var/log/blacklotus-backup.log 2>&1
   ```

## Восстановление

```bash
bash scripts/restore.sh backups/blacklotus-20260101-031500.tar.gz.gpg
```

Скрипт спросит подтверждение перед перезаписью текущей БД.

## Проверка целостности

Периодически (раз в неделю) выполняй тестовое восстановление на **другом** сервере / в docker'е:

```bash
docker run --rm -v $(pwd):/w -w /w python:3.11 bash -c \
    'apt-get update && apt-get install -y gnupg sqlite3 && bash scripts/restore.sh $ARG'
```

Проверяй, что БД читается: `sqlite3 db-data/blacklotus.db 'SELECT COUNT(*) FROM users;'`.

## Секретный ключ GPG

- **НЕ** храни на VPS.
- Локально + backup на USB / hardware-key.
- Passphrase — в менеджере паролей.
- Ротация — раз в 2 года (перешифрование старых бэкапов при необходимости).
