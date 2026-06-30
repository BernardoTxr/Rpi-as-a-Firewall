# Computer A Setup Guide (Sender)

Computer A is the **sender** whose traffic is inspected. It connects to the
Raspberry Pi over WiFi and has no other path to Computer B — everything goes
through the RPi.

```
[Computer A] --WiFi--> [ wlan0  RPi ]
              RPi-Guardian   192.168.4.1
```

## 1. Connect to the firewall's WiFi

Join the WiFi network created by the Raspberry Pi:

- **SSID:** `RPi-Guardian`
- **Password:** `guardian123`

You should receive an IP in the `192.168.4.x` range via DHCP.

```bash
ping 192.168.4.1     # the Raspberry Pi (gateway)
ping 192.168.50.2    # Computer B, reachable through the RPi
```

## 2. Run the demo scripts

All scripts target Computer B (`192.168.50.2`). Override with `TARGET=...` if
needed. Run them from the repository root on Computer A:

| # | Script | Expected dashboard result |
|---|---|---|
| 1 | `bash setup/computer_a/demo_normal.sh` | 🟢 Allowed |
| 2 | `bash setup/computer_a/demo_blacklist.sh` | 🔴 Blocked - Blacklist |
| 3 | `bash setup/computer_a/demo_signature.sh` | 🔴 Blocked - Signature |
| 4 | `bash setup/computer_a/demo_beaconing.sh` | 🔴 Blocked - Frequency (C2) |

Watch the dashboard on Computer B (`http://192.168.50.1:8501`) as each script
runs. Blocked requests never reach Computer B's HTTP server log.

## 3. How each demo triggers a stage

- **Blacklist** — sends `Host: blocked.demo`, an entry in
  [guardian/blacklist.txt](../../guardian/blacklist.txt).
- **Signature** — POSTs a body with `mining.subscribe` / `stratum+tcp`, matched
  by [guardian/signatures.txt](../../guardian/signatures.txt).
- **Beaconing** — sends 15 requests in ~22s; after 10 within the 30s window the
  source IP is flagged (see `MAX_REQUESTS` in
  [guardian/detector.py](../../guardian/detector.py)).

> HTTP-only demo: use `http://` URLs. HTTPS is not intercepted in this setup.
