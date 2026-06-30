# RPi Guardian — Out-of-Band Firewall & IDS

A Raspberry Pi placed **physically between a sender (Computer A) and a
destination (Computer B)** intercepts and inspects every packet before
forwarding it. Inspection runs entirely on the RPi, external to both hosts, so
it can't be disabled or spoofed by either. Approved packets reach B; rejected
packets are dropped and shown on a live dashboard.

See [prd.md](prd.md) for the full product spec.

## Topology

```
[Computer A — sender]
    │  WiFi  (SSID: RPi-Guardian)
    ▼
[Raspberry Pi — RPi Guardian]
    │  wlan0: 192.168.4.1/24   ← A gets DHCP here
    │  eth0:  192.168.50.1/24  → direct cable to B
    ▼
[Computer B — destination / dashboard viewer]
    192.168.50.2  ·  :80 HTTP server  ·  dashboard at http://192.168.50.1:8501
```

## How it works

```
A ──HTTP/80──> nftables redirect → mitmdump(:8080) → detector.py
                                                        │
   Stage 1 Blacklist  ─┐                                │
   Stage 2 Signature  ─┼─ blocked → 403 + SQLite + dashboard (red)
   Stage 3 Frequency  ─┘                                │
                        allowed → forward to B + dashboard (green)
```

Detection logic lives in [guardian/detector.py](guardian/detector.py); events
are persisted asynchronously by [guardian/db.py](guardian/db.py) and visualized
by the Streamlit app in [guardian/dashboard.py](guardian/dashboard.py).

## Repository layout

| Path | Purpose |
|---|---|
| [guardian/](guardian/) | Detector, async SQLite logging, Streamlit dashboard |
| [guardian/blacklist.txt](guardian/blacklist.txt) | Stage 1 — blocked hosts/IPs |
| [guardian/signatures.txt](guardian/signatures.txt) | Stage 2 — payload regexes |
| [setup/rpi/](setup/rpi/) | Raspberry Pi configs + setup/start scripts |
| [setup/computer_b/](setup/computer_b/) | Target HTTP server + dashboard viewer |
| [setup/computer_a/](setup/computer_a/) | WiFi client + demo traffic scripts |

## Setup guides (in order)

1. **Raspberry Pi** — [setup/rpi/README.md](setup/rpi/README.md)
2. **Computer B** (destination + dashboard) — [setup/computer_b/README.md](setup/computer_b/README.md)
3. **Computer A** (sender + demos) — [setup/computer_a/README.md](setup/computer_a/README.md)

## Quick start

```bash
# On the Raspberry Pi
cd setup/rpi && sudo bash setup_rpi.sh
bash start_guardian.sh

# On Computer B
sudo bash setup/computer_b/start_target.sh eth0
# then open http://192.168.50.1:8501 in a browser

# On Computer A (connected to the RPi-Guardian WiFi)
bash setup/computer_a/demo_normal.sh      # allowed (green)
bash setup/computer_a/demo_blacklist.sh   # blocked (red)
bash setup/computer_a/demo_signature.sh   # blocked (red)
bash setup/computer_a/demo_beaconing.sh   # blocked (red)
```

## Scope

- **HTTP-only** demo (TCP/80). HTTPS / SSL-bump is documented but not enabled.
- **Manual start** for the demo — no systemd auto-start.
- Detection = the 3 stages above (blacklist, signature, frequency).
