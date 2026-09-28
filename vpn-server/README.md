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
