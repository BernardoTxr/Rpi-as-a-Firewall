#!/usr/bin/env bash
# Demo 1 - Normal traffic (should be ALLOWED).
# Run on Computer A after connecting to the RPi-Guardian WiFi.
# Expected: green "Allowed" row in the dashboard, and the request reaches
# Computer B's http.server log.
set -euo pipefail

TARGET="${TARGET:-192.168.50.2}"

echo "==> Normal request to http://$TARGET/"
curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" "http://$TARGET/"
echo "Check the dashboard: expect a GREEN 'Allowed' row."
