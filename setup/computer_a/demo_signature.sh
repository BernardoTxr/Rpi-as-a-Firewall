#!/usr/bin/env bash
# Demo 3 - Malicious signature (should be BLOCKED - Stage 2).
# Sends a payload containing a Stratum mining string ('stratum+tcp' /
# 'mining.subscribe'), which matches guardian/signatures.txt. The proxy
# returns HTTP 403 before the request reaches Computer B.
set -euo pipefail

TARGET="${TARGET:-192.168.50.2}"

echo "==> Request with mining signature in the body (via $TARGET)"
curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" \
    -X POST "http://$TARGET/submit" \
    -H "Content-Type: application/json" \
    --data '{"method":"mining.subscribe","params":["stratum+tcp://pool"]}'
echo "Check the dashboard: expect a RED 'Blocked - Signature' row."
echo "(Computer B's http.server log should NOT show this request.)"
