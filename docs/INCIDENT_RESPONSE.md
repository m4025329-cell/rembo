# 🚨 План реагирования на инцидент

Читать ДО того, как всё случится.

## Быстрый чек-лист (первые 15 минут)

1. **Изолируй.** Отключи бота (`docker compose down` / `systemctl stop`).
   Останови панель 3x-ui (`x-ui stop`).
2. **Смени токен бота у @BotFather** → команда `/revoke`. Пропиши новый в `.env`, перезапусти.
3. **Сгенерируй новый `FERNET_KEY`**. ВНИМАНИЕ: старые ключи в БД станут нечитаемы; либо расшифруй старым и перезашифруй новым (см. ниже).
4. **Сгенерируй новый `JWT_SECRET`**, `PAYMENT_SECRET`, `XRAY_API_KEY`.
5. **Ротация SSH-ключей** на VPS: сгенерируй новую пару, положи в `authorized_keys`, удали старую.
6. **Ротация паролей** панели 3x-ui, GPG passphrase для бэкапов.
7. **Проверь audit.log** и `journalctl` на неавторизованные админ-действия.
8. **Проверь UFW / fail2ban**: `sudo fail2ban-client status sshd`.
9. **Уведоми пользователей** (если утекли их данные).

## Ротация Fernet-ключа

```python
# в django-shell / python
from cryptography.fernet import Fernet, MultiFernet
old = Fernet(OLD_KEY)
new = Fernet(NEW_KEY)
mf = MultiFernet([new, old])  # новый ставим первым — им будем перешифровывать
# для всех key_value: mf.rotate(token.encode())
```

Скрипт `scripts/rotate_fernet.py` сделай при необходимости — базу это не ломает.

## Компрометация VPS

1. Выкачай логи (`/var/log/auth.log`, `journalctl -u ssh`, `logs/audit.log`).
2. Сохрани snapshot диска у провайдера — форензика.
3. Пересобери сервер с нуля из `vpn-server/setup-server.sh`.
4. Восстанови БД из последнего бэкапа GPG (`scripts/restore.sh`).
5. Ротация всех секретов (см. выше).

## Компрометация ADMIN_ID (сессия Telegram)

1. Завершить все Telegram-сессии в настройках Telegram.
2. Включить 2FA (`Настройки → Конфиденциальность → Cloud password`).
3. Сменить пароль облака.
4. Проверить последние действия в `audit.log`.

## Утечка кода

- Отзыв доступа к репозиторию (проверить collaborators).
- Смена всех секретов (см. быстрый чек-лист).
- Rewrite git-истории при необходимости через `git filter-repo`.
- Force-push после согласования с командой.

## Контакты

- Владелец проекта: (заполни свой Telegram/email).
- Хостинг: (аккаунт/support-канал провайдера).
- GitHub: (owner/repo).

Держи этот файл актуальным.
