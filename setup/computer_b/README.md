# Computer B Setup Guide (Destination + Dashboard Viewer)

Computer B is the **destination** of Computer A's traffic and the machine you
use to **watch the dashboard**. It connects to the Raspberry Pi via a direct
Ethernet cable.

```
[ RPi  eth0 ] --Ethernet--> [Computer B]
   192.168.50.1               192.168.50.2
```

## 1. Prerequisites

- Linux machine with Python 3 and an Ethernet port.
- Ethernet cable from the RPi `eth0` to this machine.
- A web browser (to open the dashboard).

## 2. Start the target server

From the repository root on Computer B:

```bash
sudo bash setup/computer_b/start_target.sh eth0
```

Replace `eth0` with your Ethernet interface name if different
(check with `ip link`). The script:

1. Assigns static IP **192.168.50.2/24**.
2. Pings the RPi (192.168.50.1) to confirm the link.
3. Serves HTTP on **port 80** — this is what Computer A targets.

Keep this terminal open: allowed requests from A will appear in its log,
while blocked ones will **not** (proof the RPi dropped them).

## 3. Open the dashboard

In a browser on Computer B, go to:

```
http://192.168.50.1:8501
```

You'll see live events: green = allowed, red = blocked, with the threat
category and source IP.

## 4. Validation

| Check | Command | Expected |
|---|---|---|
| Static IP set | `ip addr show eth0` | shows `192.168.50.2` |
| Link to RPi | `ping 192.168.50.1` | reply from the RPi |
| HTTP server up | `ss -tlnp \| grep :80` | python http.server |
| Dashboard reachable | open `http://192.168.50.1:8501` | dashboard loads |
