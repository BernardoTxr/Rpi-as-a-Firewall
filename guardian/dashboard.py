"""RPi Guardian - Streamlit dashboard.

Runs on the Raspberry Pi and is opened from Computer B's browser:

    streamlit run dashboard.py --server.address 192.168.50.1 --server.port 8501

Reads events.db (the same database the detector writes to) in read-only mode.
WAL journaling lets this run concurrently with the live detector.
"""

import os
import sqlite3

import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db")
REFRESH_SECONDS = 2

CATEGORY_LABELS = {
    "blacklist": "Blocked - Blacklist",
    "signature": "Blocked - Signature",
    "beaconing": "Blocked - Frequency (C2)",
    "allowed": "Allowed",
}


def load_events():
    """Return all events as a DataFrame (newest first). Empty if no DB yet."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    # Open read-only so we never interfere with the detector's writes.
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        return pd.read_sql_query(
            "SELECT id, timestamp, src_ip, host, method, category, action "
            "FROM events ORDER BY id DESC",
            conn,
        )
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()
    finally:
        conn.close()


def _row_style(row):
    """Green background for allowed rows, red for blocked rows."""
    color = "#1b5e20" if row["action"] == "allowed" else "#7f1d1d"
    return [f"background-color: {color}; color: white"] * len(row)


def main():
    st.set_page_config(page_title="RPi Guardian", page_icon="🛡️", layout="wide")

    # Auto-refresh: prefer the dedicated helper, fall back to a meta refresh.
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(interval=REFRESH_SECONDS * 1000, key="auto")
    except ImportError:
        st.markdown(
            f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">',
            unsafe_allow_html=True,
        )

    st.title("🛡️ RPi Guardian - Traffic Monitor")
    st.caption("Out-of-band firewall + IDS - live events from Computer A → B")

    df = load_events()

    if df.empty:
        st.info("No events recorded yet. Generate traffic from Computer A.")
        return

    # --- Summary metrics ---
    total = len(df)
    blocked = int((df["action"] == "blocked").sum())
    allowed = total - blocked
    c1, c2, c3 = st.columns(3)
    c1.metric("Total events", total)
    c2.metric("Allowed", allowed)
    c3.metric("Blocked", blocked)

    by_cat = df["category"].value_counts()
    cols = st.columns(len(CATEGORY_LABELS))
    for col, (cat, label) in zip(cols, CATEGORY_LABELS.items()):
        col.metric(label, int(by_cat.get(cat, 0)))

    # --- Filters ---
    st.divider()
    f1, f2 = st.columns(2)
    categories = ["(all)"] + sorted(df["category"].unique().tolist())
    chosen_cat = f1.selectbox("Filter by category", categories)
    src_ips = ["(all)"] + sorted(df["src_ip"].unique().tolist())
    chosen_ip = f2.selectbox("Filter by source IP", src_ips)

    view = df.copy()
    if chosen_cat != "(all)":
        view = view[view["category"] == chosen_cat]
    if chosen_ip != "(all)":
        view = view[view["src_ip"] == chosen_ip]

    view = view.assign(category=view["category"].map(
        lambda c: CATEGORY_LABELS.get(c, c)
    ))

    # --- Color-coded table ---
    st.dataframe(
        view.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
