# 🛡 Меры безопасности BlackLotusVPN

Единый источник правды по защите проекта. Обновляй, когда внедряешь что-то новое.

## 1. Секреты

- Только `.env` (в `.gitignore`).
- Хардкод запрещён — `config.py` жёстко валидирует и падает при отсутствии `BOT_TOKEN` / `ADMIN_ID` / `FERNET_KEY` / `JWT_SECRET` / `WEBAPP_URL`.
- `.env.example` содержит только пустые ключи-плейсхолдеры.
- В логах секреты автоматически маскируются `SecretsFilter` (`security/logging_setup.py`).
- Pre-commit ловит `gitleaks` + `detect-secrets` + кастомные regex для tg-token, Fernet и VLESS.

## 2. База данных

- Файл SQLite лежит в `db-data/` вне репозитория, `chmod 600` ставится при инициализации.
- VPN-ключи в БД шифруются Fernet (`security/crypto.py`); `FERNET_KEY` только в `.env`.
- Пароли (когда появятся) хешируются `bcrypt cost=12` (`security/passwords.py`).
- Бэкапы: `scripts/backup.sh` дампит БД + audit-логи, шифрует GPG, опционально отправляет rsync'ом.
- Ротация: `find … -mtime +14 -delete`.

## 3. API мини-приложения

- Все `/api/*` требуют валидный `X-Init-Data` (HMAC-SHA256 c `BOT_TOKEN`, `webapp/tg_auth.py`).
- В проде (`DEBUG=false`) fallback на ADMIN_ID отсутствует — 401.
- `slowapi` держит default `RATE_LIMIT_PER_MINUTE=30/минуту на IP`, отдельные лимиты на `/api/pay` (10), `/api/support` (5).
- CORS ограничен `ALLOWED_ORIGIN` (или `WEBAPP_URL`), методы `GET/POST`, заголовки `Content-Type`, `X-Init-Data`.
- Ответы содержат: `Strict-Transport-Security`, `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`, `COOP`, `CORP`.
- OpenAPI/Swagger отключены (`docs_url=None`).
- HTTPS обязателен — терминация в nginx / Caddy + Let's Encrypt.

## 4. Бот

- Админ-команды защищены `@admin_only` (`bot/security.py`).
- `AntiFloodMiddleware` не пускает больше `BOT_FLOOD_LIMIT_PER_SECOND` (5) сообщений/сек от одного user_id.
- Все входящие данные проходят через pydantic-модели или явную валидацию (регексы, диапазоны).
- Логи проходят через `SecretsFilter`; действия админа — в `logs/audit.log`.

## 5. VPN-сервер

Скрипты в `vpn-server/`:

- `setup-server.sh`: unattended-upgrades, non-root sudo user, SSH только по ключам, `MaxAuthTries=3`, `AllowUsers`, fail2ban (`maxretry=3`, `bantime=1h`), UFW (deny all incoming, только SSH + VPN + панель).
- `install-3xui.sh`: 3x-ui на случайном порту 40000–50000, порт хранится в `/etc/blacklotus/ports.env`.
- Мониторинг — Uptime Kuma (`monitoring/`).

## 6. Обфускация (для боевой сборки)

- `scripts/obfuscate.sh` — pyarmor для критичных Python-модулей, terser + `javascript-obfuscator` для фронта.
- Артефакты в `dist_obf/` (в `.gitignore`).

## 7. Мониторинг

- Uptime Kuma в Docker (`monitoring/docker-compose.yml`).
- Telegram-алерты админу: старт бота, падение бота, 500 на API, срабатывание anti-flood, попытка доступа к админ-команде без прав.

## 8. Обновления

- `unattended-upgrades` на VPS.
- `pip install --upgrade` через `pip-audit` (добавить в CI при желании).
- Регулярно проверяй `npm audit` / `pnpm audit` для JS-инструментов обфускации.

## 9. Контроль доступа

- ADMIN_ID один. Второго админа заводить через переменную окружения (список), не в коде.
- SSH-ключи ротируются раз в 6 месяцев.
- GPG-ключ для бэкапов хранится ОТДЕЛЬНО от VPS (например, в yubikey).
