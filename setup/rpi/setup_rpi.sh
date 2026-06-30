#!/usr/bin/env bash
# RPi Guardian - one-time Raspberry Pi setup.
# Run on the Raspberry Pi:  sudo bash setup_rpi.sh
#
# Configures: packages, static IPs, IP forwarding, nftables NAT, hostapd AP,
# dnsmasq DHCP, and the Python tooling (mitmproxy via pipx, streamlit).
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo bash setup_rpi.sh" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Original (non-root) user, so pipx installs into their home.
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"

echo "==> Installing system packages..."
apt update
apt install -y hostapd dnsmasq nftables pipx python3-dev

echo "==> Stopping services while we configure them..."
systemctl stop hostapd || true
systemctl stop dnsmasq || true

echo "==> Deploying config files..."
install -m 644 "$SCRIPT_DIR/hostapd.conf"  /etc/hostapd/hostapd.conf
install -m 644 "$SCRIPT_DIR/dnsmasq.conf"  /etc/dnsmasq.conf
install -m 644 "$SCRIPT_DIR/nftables.conf" /etc/nftables.conf
grep -q 'hostapd.conf' /etc/default/hostapd || \
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd

echo "==> Assigning static IPs (eth0 -> B, wlan0 -> A)..."
ip addr replace 192.168.50.1/24 dev eth0
ip link set eth0 up
ip addr replace 192.168.4.1/24 dev wlan0
ip link set wlan0 up
# Persist across reboot via dhcpcd (Raspberry Pi OS default).
if [[ -f /etc/dhcpcd.conf ]] && ! grep -q 'RPi Guardian static' /etc/dhcpcd.conf; then
    cat >> /etc/dhcpcd.conf <<'EOF'

# --- RPi Guardian static addresses ---
interface eth0
static ip_address=192.168.50.1/24
interface wlan0
static ip_address=192.168.4.1/24
nohook wpa_supplicant
EOF
fi

echo "==> Enabling IPv4 forwarding..."
sysctl -w net.ipv4.ip_forward=1
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf || \
    echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf

echo "==> Applying nftables rules..."
nft -f /etc/nftables.conf

echo "==> Enabling AP + DHCP services..."
systemctl unmask hostapd
systemctl enable hostapd dnsmasq nftables
systemctl restart hostapd dnsmasq

echo "==> Installing Python tooling for $REAL_USER..."
sudo -u "$REAL_USER" env PATH="$REAL_HOME/.local/bin:$PATH" pipx install mitmproxy || \
    sudo -u "$REAL_USER" env PATH="$REAL_HOME/.local/bin:$PATH" pipx upgrade mitmproxy
sudo -u "$REAL_USER" python3 -m pip install --user --break-system-packages \
    streamlit pandas

echo
echo "Setup complete. Next:"
echo "  1) Connect Computer A to WiFi 'RPi-Guardian' (pass: guardian123)."
echo "  2) Set Computer B static IP 192.168.50.2/24 and start its HTTP server."
echo "  3) Run: bash $SCRIPT_DIR/start_guardian.sh"
