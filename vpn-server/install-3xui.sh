#!/usr/bin/env bash
# Установка панели 3x-ui на нестандартном порту.
# Читает PANEL_PORT из /etc/blacklotus/ports.env (создаётся setup-server.sh).
set -euo pipefail

if [[ -f /etc/blacklotus/ports.env ]]; then
    # shellcheck disable=SC1091
    source /etc/blacklotus/ports.env
fi
: "${PANEL_PORT:=$((40000 + RANDOM % 10000))}"

echo "== Установка 3x-ui на порту $PANEL_PORT =="

bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

# Пропишем порт панели
x-ui setting -port "$PANEL_PORT"

echo
echo "Панель установлена. Открой https://<server-ip>:$PANEL_PORT"
echo "Не забудь сразу сменить логин/пароль (x-ui → 6)."
