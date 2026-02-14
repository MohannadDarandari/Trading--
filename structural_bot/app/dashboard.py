import sqlite3
import pandas as pd
import streamlit as st
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "polyscan_live.db"

st.set_page_config(page_title="Structural Bot Dashboard", layout="wide")


def load_df(table: str, limit: int = 200) -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC LIMIT {limit}", conn)
    conn.close()
    return df


st.title("Polymarket Structural Bot")

page = st.sidebar.radio("Pages", ["Overview", "Live Orders / Fills", "Incidents", "Charts"])

if page == "Overview":
    scans = load_df("scans", 500)
    orders = load_df("orders", 200)
    fills = load_df("fills", 200)
    incidents = load_df("incidents", 200)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scans (last 2h)", len(scans))
    c2.metric("Orders", len(orders))
    c3.metric("Fills", len(fills))
    c4.metric("Incidents", len(incidents))

    st.subheader("Recent Scans")
    st.dataframe(scans.head(50))

elif page == "Live Orders / Fills":
    st.subheader("Orders")
    st.dataframe(load_df("orders", 200))
    st.subheader("Fills")
    st.dataframe(load_df("fills", 200))

elif page == "Incidents":
    st.subheader("Incidents")
    st.dataframe(load_df("incidents", 200))

elif page == "Charts":
    scans = load_df("scans", 2000)
    if not scans.empty and "unit_cost" in scans:
        st.subheader("Unit Cost vs Threshold")
        scans = scans.sort_values("id")
        st.line_chart(scans[["unit_cost", "threshold"]])

    st.subheader("Latency (ms)")
    if not scans.empty and "latency_ms" in scans:
        st.line_chart(scans[["latency_ms"]])
