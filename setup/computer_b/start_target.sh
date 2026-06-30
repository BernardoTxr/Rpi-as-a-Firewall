#!/usr/bin/env bash
# RPi Guardian - Computer B (destination / target server).
# Run on Computer B:  sudo bash start_target.sh [ETH_IFACE]
#
# Sets the static IP 192.168.50.2/24 on the Ethernet interface connected to the
# Raspberry Pi, then serves a simple HTTP site on port 80 (the target of A's
# traffic). Open the dashboard separately at http://192.168.50.1:8501.
set -euo pipefail

IFACE="${1:-eth0}"
IP="192.168.50.2/24"

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo bash start_target.sh [iface]" >&2
    exit 1
fi

echo "==> Assigning $IP to $IFACE ..."
ip addr replace "$IP" dev "$IFACE"
ip link set "$IFACE" up

echo "==> Verifying link to the Raspberry Pi (192.168.50.1) ..."
ping -c 2 -W 2 192.168.50.1 || echo "  (no reply yet - check the cable / RPi)"

echo "==> Starting HTTP server on port 80 (Ctrl+C to stop) ..."
echo "    Dashboard: open http://192.168.50.1:8501 in a browser."
exec python3 -m http.server 80
