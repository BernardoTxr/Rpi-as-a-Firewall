"""SQLite event storage for RPi Guardian.

Provides non-blocking event logging: events are pushed onto an in-memory
queue and persisted to disk by a dedicated background thread. This keeps the
mitmproxy network thread from ever stalling on disk I/O.

The same database file (events.db) is read by the Streamlit dashboard. WAL
mode is enabled so the dashboard can read while the detector writes.
"""

import os
import queue
import sqlite3
import threading
from datetime import datetime

# events.db lives next to this file so both detector.py and dashboard.py
# resolve the exact same path regardless of the working directory.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db")

# Sentinel pushed onto the queue to ask the writer thread to stop.
_STOP = object()

# Queue of pending events and the worker that drains it.
_event_queue: "queue.Queue" = queue.Queue()
_writer_thread = None
_writer_lock = threading.Lock()


def init_db():
    """Create the events table and enable WAL mode (idempotent)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT    NOT NULL,
                src_ip    TEXT    NOT NULL,
                host      TEXT    NOT NULL,
                method    TEXT,
                category  TEXT,   -- blacklist | signature | beaconing | allowed
                action    TEXT    -- blocked | allowed
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _writer_loop():
    """Background thread: pull events off the queue and write them to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        while True:
            item = _event_queue.get()
            if item is _STOP:
                break
            try:
                conn.execute(
                    "INSERT INTO events "
                    "(timestamp, src_ip, host, method, category, action) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    item,
                )
                conn.commit()
            except sqlite3.Error as exc:  # keep the thread alive on bad rows
                print(f"[guardian.db] write failed: {exc}")
            finally:
                _event_queue.task_done()
    finally:
        conn.close()


def start_writer():
    """Start the background writer thread once. Safe to call repeatedly."""
    global _writer_thread
    with _writer_lock:
        if _writer_thread is None or not _writer_thread.is_alive():
            init_db()
            _writer_thread = threading.Thread(
                target=_writer_loop, name="guardian-db-writer", daemon=True
            )
            _writer_thread.start()


def log_event(src_ip, host, method, category, action):
    """Queue an event for asynchronous persistence (non-blocking)."""
    timestamp = datetime.now().isoformat(timespec="seconds")
    _event_queue.put((timestamp, src_ip, host, method, category, action))


def stop_writer():
    """Flush the queue and stop the writer thread (used on shutdown)."""
    if _writer_thread is not None and _writer_thread.is_alive():
        _event_queue.put(_STOP)
        _writer_thread.join(timeout=5)
