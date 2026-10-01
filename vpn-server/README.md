# 🕸 VPN-сервер BlackLotusVPN

Хранит скрипты установки/hardening'а для VPS, на котором крутится
3x-ui и Xray-ядро. Реальные `keys/` и бэкапы **не коммитятся**.

## Быстрый старт

```bash
# 1. На чистой Ubuntu 22.04/Debian 12 (от root):
export SSH_PUBKEY='ssh-ed25519 AAAAC3... user@host'
export NEW_USER=blackops
bash setup-server.sh

# 2. Разлогинься и залогинься под NEW_USER (проверь, что работает).

# 3. Установи панель:
sudo bash install-3xui.sh

# 4. Открой https://<ip>:<PANEL_PORT>, смени логин/пароль,
#    сгенерируй inbound на порту 443 (VLESS + Reality).
```

## Подключить панель к боту

После шага 4 бот ещё не знает о сервере и выдаёт DEMO-ключи. Чтобы
переключить на боевые — впиши в `.env` (см. `.env.example`):

| Переменная | Где взять |
| :--------- | :-------- |
| `XUI_PANEL_URL` | `https://<ip>:<PANEL_PORT>` панели |
| `XUI_USERNAME` / `XUI_PASSWORD` | логин/пароль панели (сменил в шаге 4) |
| `XUI_INBOUND_ID` | список инбаундов в панели → id созданного VLESS+Reality |
| `XUI_SERVER_HOST` | IP или домен, который увидит клиент (не обязательно = IP панели) |
| `XUI_SERVER_PORT` | порт inbound'а (обычно 443) |
| `XUI_REALITY_PUBLIC_KEY`, `XUI_REALITY_SHORT_ID`, `XUI_REALITY_SNI` | открой inbound в панели → «Reality settings» — там публичный ключ, short ID и target (sni) |
| `XUI_FLOW` | обычно `xtls-rprx-vision` — смотри, что выбрано у клиента в том же inbound |

Перезапусти бота — `/api/keys` и кнопка «Создать ключ» в мини-приложении
начнут выдавать реальные VLESS-ссылки вместо `DEMO-*`.

Один `.env` = одна панель/сервер (MVP). Для нескольких стран — несколько
физических серверов потребуют расширения `webapp/xui.py` под карту
`{country: XUI-конфиг}` вместо плоских переменных.

## Что делает setup-server.sh

| Шаг | Действие |
| :-: | :------- |
| 1 | `apt upgrade` + `unattended-upgrades` (авто security-апдейты + ребут в 04:15) |
| 2 | Создаёт `NEW_USER` в sudo, кладёт `SSH_PUBKEY` в `authorized_keys` (600) |
| 3 | SSH: `PermitRootLogin no`, `PasswordAuthentication no`, `MaxAuthTries 3`, `AllowUsers $NEW_USER` |
| 4 | `fail2ban`: `maxretry=3`, `bantime=1h`, backend systemd, action ufw |
| 5 | UFW: default deny in, разрешены только SSH + VPN + панель (панель на случайном порту 40000–50000) |

Выбранные порты сохраняются в `/etc/blacklotus/ports.env`.

## После установки

- Проверь `sudo fail2ban-client status sshd`.
- Проверь `sudo ufw status`.
- Проверь `sudo unattended-upgrade --dry-run --debug`.
- Впиши в мониторинг (см. `../monitoring/`) health-check на панель.
- Забэкапь `/etc/blacklotus/` и `/usr/local/x-ui/` — см. `../scripts/backup.sh`.

## Что коммитить нельзя

- Реальные `keys/*.key`, `*.pem`, конфиги с UUID'ами.
- `subscribe/`, `backups/`, дампы БД панели.

Всё это в `.gitignore` под `vpn-server/`.
