# 🖤 BlackLotusVPN

## ⚠️ Приватный код, все права защищены

**Copyright © 2026 BlackLotusVPN.** Проект является проприетарным.
Запрещено копировать, использовать, распространять и модифицировать код
без письменного разрешения правообладателя. Полный текст — в
[`LICENSE.md`](LICENSE.md). Политика безопасности — в [`SECURITY.md`](SECURITY.md).

Telegram-бот + мини-приложение для продажи VPN-подписок. Тёмная Halloween-тема: чёрный лотос, оранжевые всполохи, фиолетовое свечение и призраки.

Стек:

- **Python 3.11**, **aiogram 3.x** — бот
- **FastAPI + Uvicorn** — бэкенд мини-приложения (Telegram WebApp)
- **SQLAlchemy 2 (async) + aiosqlite / SQLite** — БД для MVP
- **HTML/CSS/JS** — фронт мини-приложения (шрифты Creepster + Inter, SVG-иконки)
- **Docker + docker-compose** — деплой

Внутри реализованы заглушки: платёж моментально активирует подписку, VPN-ключ — случайный UUID в формате `vless://…`, список серверов hardcode-нутый (5 стран).

---

## 📁 Структура проекта

```
.
├── bot/                # Telegram-бот (aiogram 3)
│   ├── main.py         # точка входа бота
│   ├── handlers.py     # /start /help /status
│   ├── admin.py        # /admin: статистика, рассылка, выдача/отзыв
│   └── keyboards.py
├── webapp/             # мини-приложение
│   ├── main.py         # FastAPI + REST API
│   ├── tg_auth.py      # валидация initData Telegram WebApp
│   ├── templates/index.html
│   └── static/         # CSS, JS, SVG-иконки
├── db/                 # ORM-модели и репозиторий
│   ├── database.py
│   ├── models.py
│   └── repo.py
├── docker/             # Dockerfile и compose-файл
├── config.py           # общие настройки (pydantic-settings)
├── run.py              # запуск бота + вебапа в одном процессе
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Запуск локально

1. Скопируй `.env.example` в `.env` и подставь свой `BOT_TOKEN` и `ADMIN_ID`:

   ```bash
   cp .env.example .env
   ```

2. Создай виртуальное окружение и установи зависимости:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Запусти бота + вебап одной командой:

   ```bash
   python run.py
   ```

   FastAPI будет доступен на `http://localhost:8080/` (мини-приложение), бот запустится в polling-режиме.

4. Отдельные запуски (если нужно):

   ```bash
   python -m bot.main                                  # только бот
   uvicorn webapp.main:app --host 0.0.0.0 --port 8080  # только вебап
   ```

---

## 🌐 Как открыть мини-приложение в Telegram

Мини-приложение работает через кнопку `WebApp`, поэтому URL из `.env` (`WEBAPP_URL`) обязан быть **HTTPS** и публично доступен.

Быстрые варианты:

- **Cloudflare Tunnel** / **ngrok**:

  ```bash
  cloudflared tunnel --url http://localhost:8080
  # или
  ngrok http 8080
  ```

  Полученный HTTPS-URL пропиши в `WEBAPP_URL=` в `.env`, перезапусти бота, отправь `/start` и жми «🖤 Открыть BlackLotusVPN».

- **Свой сервер** с nginx + Let's Encrypt: проксируй `https://your-domain/` на `http://localhost:8080`.

Дополнительно можно зарегистрировать мини-приложение в [@BotFather](https://t.me/BotFather) → `/newapp`, чтобы кнопка появлялась во всех клиентах.

---

## 🐳 Деплой через docker-compose

```bash
cp .env.example .env
# отредактируй .env

docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml logs -f
```

- FastAPI будет проброшен на `:8080`.
- SQLite-файл лежит в `./db-data/blacklotus.db` (volume).
- Останов: `docker compose -f docker/docker-compose.yml down`.

Далее направь домен на `:8080` через nginx / Caddy / Traefik c HTTPS и укажи этот домен в `WEBAPP_URL`.

Пример nginx-фрагмента:

```nginx
server {
    server_name vpn.example.com;
    listen 443 ssl http2;
    ssl_certificate     /etc/letsencrypt/live/vpn.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vpn.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## 🛠 Админка бота

Команда `/admin` (только для пользователя с `ADMIN_ID` из `.env`) даёт четыре кнопки:

- **📊 Статистика** — количество юзеров, активные подписки, суммарный доход.
- **📣 Рассылка** — следующим сообщением отправишь текст, бот разошлёт его всем.
- **🎫 Выдать подписку** — формат `<tg_id> <plan>`, где `plan` = `1m` / `3m` / `12m`.
- **🚫 Отозвать подписку** — `<tg_id>`.

Отмена любой формы: `/cancel`.

---

## 🎨 Дизайн

- Фон `#0a0a0a`, акценты: оранжевый `#ff6b1a` и фиолетовый `#6a0dad`.
- Шрифты: **Creepster** (заголовки) и **Inter** (текст) — подключены с Google Fonts.
- Иконки: чёрный лотос, летучие мыши, призраки — как inline-SVG в `webapp/static/img/icons.svg`.
- Летучие мыши плавно летают на фоне за счёт CSS-анимаций.

---

## 🔒 Безопасность

- Все обращения к `/api/*` защищены проверкой `initData` от Telegram WebApp (HMAC-SHA256 с секретом на базе `BOT_TOKEN`).
- В dev-режиме (открыв мини-приложение прямо в браузере без Telegram) API работает от имени `ADMIN_ID` — удобно для отладки. **В проде не оставляй этот fallback** или закрой доступ по домену.

---

## 👤 Личный кабинет: вход по email/телефону

Если мини-приложение открыто не из Telegram (initData нет), показывается
экран входа/регистрации: email или телефон + пароль.

- Регистрация → код подтверждения (6 цифр, 10 минут) на почту/SMS → ввод
  кода выдаёт токен личного кабинета (хранится в `localStorage`, 30 дней).
- Повторная отправка кода — не чаще раза в минуту, 5 неверных попыток —
  код нужно запросить заново.
- Без `SMTP_*`/`SMS_RU_API_ID` в `.env` код просто пишется в лог процесса
  (`logs/app.log`) — можно тестировать локально без реальной почты/SMS.
  Что вставить для боевой отправки — см. `.env.example`.
- Этот вход независим от Telegram-аккаунта: внутри Telegram всё работает
  по-старому через `initData`, без паролей.

---

## 🗺 Что заменить дальше

- **Оплата**: `POST /api/pay` (см. `webapp/main.py`) → интегрировать ЮKassa / Telegram Stars / Crypto.
- **Генерация ключей**: `db/repo.py::generate_key` → вызовы к панели VPN (3x-ui, Marzban, Sing-box API).
- **Список серверов**: `db/repo.py::SERVERS` — сейчас hardcode, потом можно вытаскивать из панели.
- **Миграции**: для MVP используется `Base.metadata.create_all`. При росте схемы — переезд на Alembic.

---

## 🔒 Безопасность и правила коммитинга

Полная политика — [`docs/SECURITY.md`](docs/SECURITY.md), реагирование — [`docs/INCIDENT_RESPONSE.md`](docs/INCIDENT_RESPONSE.md), бэкапы — [`docs/BACKUP.md`](docs/BACKUP.md).

Кратко:

- **Никогда не коммить**: `.env`, `*.db`, `*.log`, `*.key`, `*.pem`, `config.local.*`, `vpn-server/keys/*`. Всё в `.gitignore`.
- **Перед первым коммитом** установи pre-commit хуки:

  ```bash
  bash scripts/install-precommit.sh
  ```

  `gitleaks` + `detect-secrets` завернут коммит с любым секретом.

- **Секреты только через `.env`** — `config.py` валидирует и падает при отсутствии `BOT_TOKEN`, `ADMIN_ID`, `FERNET_KEY`, `JWT_SECRET`, `WEBAPP_URL`.
- **Генерация FERNET_KEY**:

  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- **Прод-режим**: `DEBUG=false`, `WEBAPP_URL` только по HTTPS, `ALLOWED_ORIGIN` == домен WebApp.
- **VPN-сервер**: разверни через `vpn-server/setup-server.sh` (SSH только по ключу, UFW, fail2ban, unattended-upgrades). Порт панели 3x-ui случайный 40000–50000.
- **Бэкапы**: `bash scripts/backup.sh` (GPG-шифрование). Крон-строка в `docs/BACKUP.md`.
- **Обфускация**: `bash scripts/obfuscate.sh` (pyarmor + terser + javascript-obfuscator).
- **Мониторинг**: Uptime Kuma — `docker compose -f monitoring/docker-compose.yml up -d`.

Happy Halloween 🎃🖤
