#!/usr/bin/env bash
# Demo 4 - Beaconing / C2 frequency (should be BLOCKED - Stage 3).
# Fires 15 requests to the same host within ~30s. After more than 10 requests
# in the 30s window, the proxy flags the source IP as beaconing and starts
# returning HTTP 403.
set -euo pipefail

TARGET="${TARGET:-192.168.50.2}"
COUNT="${COUNT:-15}"
DELAY="${DELAY:-1.5}"  # seconds between requests (15 x 1.5s ~= 22s < 30s window)

echo "==> Sending $COUNT requests to http://$TARGET/ ($DELAY s apart)"
for i in $(seq 1 "$COUNT"); do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://$TARGET/beacon")
    echo "  request $i -> HTTP $code"
    sleep "$DELAY"
done
echo "Check the dashboard: later requests should turn RED 'Blocked - Frequency (C2)'."
