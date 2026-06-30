"""RPi Guardian - mitmproxy detection addon (3-stage filtering).

Loaded by mitmdump in transparent mode:

    mitmdump --mode transparent -s detector.py --listen-port 8080

Inspection pipeline (per PRD section 13):
  Stage 1 - Blacklist : request host matches a known-bad host/IP  -> block
  Stage 2 - Signature : a regex matches the request URL/headers/body -> block
  Stage 3 - Frequency : > MAX_REQUESTS to a host in WINDOW seconds  -> block

Allowed requests are forwarded to Computer B and logged as "allowed".
Every decision is persisted asynchronously to events.db (see db.py).
"""

import os
import re
import time
from collections import defaultdict, deque

from mitmproxy import http

import db

# --- Tunables -------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
BLACKLIST_PATH = os.path.join(_HERE, "blacklist.txt")
SIGNATURES_PATH = os.path.join(_HERE, "signatures.txt")

# Stage 3: beaconing heuristic.
WINDOW_SECONDS = 30
MAX_REQUESTS = 10  # more than this within WINDOW_SECONDS is treated as C2.

# --- State loaded at startup ---------------------------------------------
BLACKLIST = set()
SIGNATURE_RE = None

# Per source-IP sliding window of request timestamps (Stage 3).
_request_log = defaultdict(deque)


def _load_blacklist(path):
    """Read blacklist.txt into a lowercase set of hosts/IPs."""
    hosts = set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    hosts.add(line.lower())
    except FileNotFoundError:
        print(f"[guardian] blacklist not found: {path}")
    return hosts


def _load_signatures(path):
    """Compile signatures.txt into a single case-insensitive regex."""
    patterns = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except FileNotFoundError:
        print(f"[guardian] signatures not found: {path}")
    if not patterns:
        return None
    combined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(combined, re.IGNORECASE)


def load():
    """Populate detection state. Called by load() hook and at import time."""
    global BLACKLIST, SIGNATURE_RE
    BLACKLIST = _load_blacklist(BLACKLIST_PATH)
    SIGNATURE_RE = _load_signatures(SIGNATURES_PATH)
    db.start_writer()
    print(
        f"[guardian] loaded {len(BLACKLIST)} blacklist entries, "
        f"signatures {'enabled' if SIGNATURE_RE else 'disabled'}"
    )


def _client_ip(flow):
    """Best-effort source IP of Computer A behind the transparent proxy."""
    conn = flow.client_conn
    peer = getattr(conn, "peername", None)
    if peer:
        return peer[0]
    # Fallback for older mitmproxy versions.
    addr = getattr(conn, "address", None)
    if addr:
        return addr[0]
    return "unknown"


def _inspectable_text(flow):
    """Concatenate URL, headers and body for signature scanning."""
    req = flow.request
    parts = [req.pretty_url]
    parts.extend(f"{k}: {v}" for k, v in req.headers.items())
    try:
        parts.append(req.get_text(strict=False) or "")
    except (ValueError, UnicodeDecodeError):
        pass  # binary/undecodable body - skip it
    return "\n".join(parts)


def _block(flow, reason, category):
    """Replace the flow with a 403 and log the blocked event."""
    flow.response = http.Response.make(
        403, f"Blocked: {reason}".encode(), {"Content-Type": "text/plain"}
    )
    db.log_event(
        src_ip=_client_ip(flow),
        host=flow.request.pretty_host,
        method=flow.request.method,
        category=category,
        action="blocked",
    )


def _record_request(src_ip):
    """Append a timestamp to the source IP's sliding window."""
    now = time.monotonic()
    log = _request_log[src_ip]
    log.append(now)
    cutoff = now - WINDOW_SECONDS
    while log and log[0] < cutoff:
        log.popleft()


def _is_beaconing(src_ip):
    """True if the source IP exceeded MAX_REQUESTS within the window."""
    return len(_request_log[src_ip]) > MAX_REQUESTS


# --- mitmproxy event hooks ------------------------------------------------
def request(flow: http.HTTPFlow):
    """Run blacklist + signature stages, and feed the frequency counter."""
    host = flow.request.pretty_host

    # Stage 1 - Blacklist.
    if host.lower() in BLACKLIST:
        _block(flow, "blacklist", "blacklist")
        return

    # Stage 2 - Signature.
    if SIGNATURE_RE is not None and SIGNATURE_RE.search(_inspectable_text(flow)):
        _block(flow, "signature", "signature")
        return

    # Stage 3 - record for frequency analysis (decision made in response()).
    _record_request(_client_ip(flow))


def response(flow: http.HTTPFlow):
    """Apply the frequency stage; otherwise log the request as allowed."""
    # If a previous stage already blocked it, that response is our 403.
    if flow.response is not None and flow.response.status_code == 403:
        return

    src_ip = _client_ip(flow)
    if _is_beaconing(src_ip):
        _block(flow, "beaconing (C2)", "beaconing")
        return

    db.log_event(
        src_ip=src_ip,
        host=flow.request.pretty_host,
        method=flow.request.method,
        category="allowed",
        action="allowed",
    )


# Load detection state when imported by mitmdump.
load()
