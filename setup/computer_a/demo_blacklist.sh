#!/usr/bin/env bash
# Demo 2 - Blacklisted host (should be BLOCKED - Stage 1).
# Sends a request whose Host header is 'blocked.demo', which is listed in
# guardian/blacklist.txt. The transparent proxy matches the host and returns
# HTTP 403 before the request ever reaches Computer B.
set -euo pipefail

TARGET="${TARGET:-192.168.50.2}"
BAD_HOST="blocked.demo"

echo "==> Request to blacklisted host '$BAD_HOST' (via $TARGET)"
curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" \
    --resolve "$BAD_HOST:80:$TARGET" "http://$BAD_HOST/"
echo "Check the dashboard: expect a RED 'Blocked - Blacklist' row."
echo "(Computer B's http.server log should NOT show this request.)"
