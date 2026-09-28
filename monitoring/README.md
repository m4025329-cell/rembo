# 📈 Мониторинг BlackLotusVPN

## Uptime Kuma

```bash
docker compose -f monitoring/docker-compose.yml up -d
```

По умолчанию биндится на `127.0.0.1:3001` — проброс наружу делай через
nginx с basic-auth и HTTPS.

Что мониторить:

- HTTP-check на `https://<webapp-domain>/api/plans` (5 сек, каждые 30 сек).
- HTTP-check на `https://<panel-domain>:<PANEL_PORT>/panel/api/…`.
- Ping VPS-сервера.
- TCP-check на порт VPN (443/tcp).
- Alerts → Telegram bot (тот же `BOT_TOKEN`, отдельный chat).

## Алерты из приложения

Приложение уже шлёт админу в Telegram:

- при старте бота;
- при фатальной ошибке в поллинге;
- при ответе 500 из API мини-приложения;
- при попытке доступа к админ-команде с чужого user_id (audit-лог);
- при anti-flood срабатывании (audit).

Всё пишется в `logs/audit.log` (структурированные строки).

## Расширения (по желанию)

- Prometheus + Grafana для метрик (RPS, latency, %ошибок).
- Loki + Promtail для агрегации `logs/app.log` и `logs/audit.log`.
- Sentry для трейсбэков (для этого добавь `sentry-sdk` в requirements).
