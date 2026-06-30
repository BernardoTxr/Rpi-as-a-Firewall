# Raspberry Pi Setup Guide (RPi Guardian)

The Raspberry Pi sits **physically between Computer A and Computer B** and
inspects every packet. It runs a WiFi access point for A, an inspection proxy,
and the dashboard.

```
[Computer A] --WiFi--> [ wlan0  RPi  eth0 ] --Ethernet--> [Computer B]
                         192.168.4.1        192.168.50.1
```

## 1. Prerequisites

- Raspberry Pi 3B+ or newer with built-in WiFi, running Raspberry Pi OS Lite (64-bit).
- Ethernet cable from the RPi `eth0` directly to Computer B.
- This repository copied onto the RPi (e.g. in `~/Rpi-as-a-Firewall`).

## 2. One-time setup

From the repository root on the RPi:

```bash
cd setup/rpi
sudo bash setup_rpi.sh
```

This installs packages, assigns static IPs (`eth0` 192.168.50.1, `wlan0`
192.168.4.1), enables IP forwarding, deploys the `hostapd`, `dnsmasq` and
`nftables` configs, starts the WiFi access point + DHCP, and installs
`mitmproxy` (via pipx) and `streamlit`.

> The WiFi network is **SSID `RPi-Guardian`**, password **`guardian123`**
> (change these in [hostapd.conf](hostapd.conf)).

## 3. Start the firewall + dashboard

```bash
bash setup/rpi/start_guardian.sh
```

This launches:

- `mitmdump` (transparent mode) on port **8080**, running
  [guardian/detector.py](../../guardian/detector.py)
- the Streamlit dashboard on **http://192.168.50.1:8501**

Leave this running during the demo. Press `Ctrl+C` to stop both.

## 4. Validation

| Check | Command | Expected |
|---|---|---|
| eth0 → B | `ping 192.168.50.2` | reply from B |
| IP forwarding | `cat /proc/sys/net/ipv4/ip_forward` | `1` |
| NAT rules | `sudo nft list ruleset` | prerouting redirect + postrouting masquerade |
| Proxy listening | `ss -tlnp \| grep 8080` | mitmdump process |
| Dashboard listening | `ss -tlnp \| grep 8501` | streamlit process |

## 5. Detection tuning

- Blocked hosts: [guardian/blacklist.txt](../../guardian/blacklist.txt)
- Payload regexes: [guardian/signatures.txt](../../guardian/signatures.txt)
- Beaconing thresholds: `MAX_REQUESTS` / `WINDOW_SECONDS` in
  [guardian/detector.py](../../guardian/detector.py)

Restart `start_guardian.sh` after editing these files.

## Notes

- **HTTP-only demo.** Only TCP/80 is redirected into the proxy. HTTPS
  interception (SSL bump) would require installing the mitmproxy CA on
  Computer A and redirecting TCP/443; it is intentionally out of scope here.
- **No auto-start.** Services are started manually for the demo. To survive a
  reboot you would add systemd units, which is not covered here.
