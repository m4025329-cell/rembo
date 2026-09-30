#!/usr/bin/env bash
# Один запуск: бот + вебапп + бесплатный HTTPS-туннель Cloudflare.
# Сам прописывает WEBAPP_URL и ALLOWED_ORIGIN в .env. Домен не нужен.
# ponytail: quick-tunnel URL меняется при каждом старте (скрипт это учитывает);
# для постоянного адреса — свой домен + nginx/Caddy (см. README).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Нет .env: cp .env.example .env и заполни токены"; exit 1; }

PORT=$(grep -E '^WEBAPP_PORT=' .env | cut -d= -f2 || true); PORT=${PORT:-8080}

if ! command -v cloudflared >/dev/null; then
  arch=$(uname -m); [ "$arch" = "x86_64" ] && arch=amd64 || arch=arm64
  mkdir -p .bin
  curl -fsSL -o .bin/cloudflared \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$arch"
  chmod +x .bin/cloudflared; export PATH="$PWD/.bin:$PATH"
fi

pkill -f "[r]un.py" 2>/dev/null || true
pkill -f "[c]loudflared tunnel" 2>/dev/null || true
: > logs/tunnel.log 2>/dev/null || { mkdir -p logs; : > logs/tunnel.log; }
nohup cloudflared tunnel --url "http://localhost:$PORT" >logs/tunnel.log 2>&1 &

for _ in $(seq 1 30); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' logs/tunnel.log | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "${URL:-}" ] || { echo "Туннель не поднялся, смотри logs/tunnel.log"; exit 1; }

setenv() { grep -qE "^$1=" .env && sed -i "s|^$1=.*|$1=$2|" .env || echo "$1=$2" >> .env; }
setenv WEBAPP_URL "$URL"; setenv ALLOWED_ORIGIN "$URL"

nohup python run.py >logs/app.log 2>&1 &
echo "Готово. WEBAPP_URL=$URL"
echo "Логи: logs/app.log. Отправь боту /start и открой мини-приложение."
