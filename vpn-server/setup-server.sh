#!/usr/bin/env bash
# =====================================================================
#  BlackLotusVPN — hardening скрипт свежего VPS (Ubuntu 22.04/Debian 12)
#
#  Что делает:
#   1. Обновляет систему, ставит unattended-upgrades.
#   2. Создаёт non-root sudo-пользователя.
#   3. Настраивает SSH: только ключи, отключает root-логин.
#   4. Ставит fail2ban с баном после 3 неудачных попыток.
#   5. Настраивает UFW: SSH, HTTPS, VPN-порт, панель на нестандартном порту.
#
#  Запускать один раз от root'а. Внимательно проверь SSH-ключ до
#  перезапуска sshd — иначе можно потерять доступ.
# =====================================================================
set -euo pipefail

# ── Параметры (можно переопределить через env) ────────────────────
: "${NEW_USER:=blackops}"
: "${SSH_PUBKEY:?Задай SSH_PUBKEY='ssh-ed25519 AAAA...' перед запуском}"
: "${SSH_PORT:=22}"
: "${VPN_PORT:=443}"
# Случайный порт панели 3x-ui из диапазона 40000-50000
if [[ -z "${PANEL_PORT:-}" ]]; then
    PANEL_PORT=$(( 40000 + RANDOM % 10000 ))
fi

echo "== BlackLotusVPN hardening =="
echo "user=$NEW_USER  ssh_port=$SSH_PORT  vpn_port=$VPN_PORT  panel_port=$PANEL_PORT"

# ── 1. Обновление и unattended-upgrades ────────────────────────────
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -y install unattended-upgrades fail2ban ufw curl wget vim git \
                   gnupg openssl chrony
dpkg-reconfigure -f noninteractive unattended-upgrades

cat >/etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:15";
EOF

# ── 2. Non-root sudo user ─────────────────────────────────────────
if ! id "$NEW_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$NEW_USER"
    usermod -aG sudo "$NEW_USER"
fi
install -d -m 700 -o "$NEW_USER" -g "$NEW_USER" "/home/$NEW_USER/.ssh"
echo "$SSH_PUBKEY" > "/home/$NEW_USER/.ssh/authorized_keys"
chmod 600 "/home/$NEW_USER/.ssh/authorized_keys"
chown "$NEW_USER:$NEW_USER" "/home/$NEW_USER/.ssh/authorized_keys"

# passwordless sudo для установки/апдейтов (можно ужесточить позже)
echo "$NEW_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$NEW_USER"
chmod 440 "/etc/sudoers.d/90-$NEW_USER"

# ── 3. SSH hardening ──────────────────────────────────────────────
SSHD=/etc/ssh/sshd_config.d/90-blacklotus.conf
cat > "$SSHD" <<EOF
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
X11Forwarding no
AllowUsers $NEW_USER
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
chmod 600 "$SSHD"
sshd -t && systemctl reload ssh

# ── 4. fail2ban ────────────────────────────────────────────────────
cat >/etc/fail2ban/jail.d/blacklotus.local <<EOF
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 3
banaction = ufw
backend   = systemd

[sshd]
enabled  = true
port     = $SSH_PORT
mode     = aggressive
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

# ── 5. UFW firewall ──────────────────────────────────────────────
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT"/tcp comment 'SSH'
ufw allow "$VPN_PORT"/tcp comment 'VPN (TLS)'
ufw allow "$VPN_PORT"/udp comment 'VPN (UDP fallback)'
ufw allow "$PANEL_PORT"/tcp comment '3x-ui panel'
ufw --force enable

# Сохраним выбранные порты для последующих скриптов
mkdir -p /etc/blacklotus
cat >/etc/blacklotus/ports.env <<EOF
SSH_PORT=$SSH_PORT
VPN_PORT=$VPN_PORT
PANEL_PORT=$PANEL_PORT
EOF
chmod 600 /etc/blacklotus/ports.env

echo
echo "✅ Hardening завершён."
echo "   SSH:   $SSH_PORT (только ключом, только пользователь $NEW_USER)"
echo "   Панель: :$PANEL_PORT — сохранён в /etc/blacklotus/ports.env"
echo "Проверь новый ssh-логин из ДРУГОГО терминала, ПРЕЖДЕ ЧЕМ закрывать это окно."
