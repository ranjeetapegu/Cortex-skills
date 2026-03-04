import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Cortex AI Cost Dashboard",
    page_icon="snowflake",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar: shared filters ──────────────────────────────────────────────────
st.sidebar.title("Cortex AI Cost Dashboard")
st.sidebar.markdown("---")

# Date range
st.sidebar.subheader("Date Range")
default_end = datetime.today().date()
default_start = default_end - timedelta(days=30)

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("From", value=default_start, key="global_start")
end_date = col2.date_input("To", value=default_end, key="global_end")

if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")

# Service filter
ALL_SERVICES = [
    "AI Functions",
    "Cortex Analyst",
    "Cortex Agents",
    "Cortex Search",
    "Document Processing",
    "Cortex Code CLI",
    "Fine-Tuning",
    "REST API",
]
st.sidebar.subheader("Service Filter")
selected_services = st.sidebar.multiselect(
    "Select services to include",
    options=ALL_SERVICES,
    default=ALL_SERVICES,
    key="global_services",
)

st.sidebar.markdown("---")
st.sidebar.caption("Data source: SNOWFLAKE.ACCOUNT_USAGE")
st.sidebar.caption("Cache TTL: 10 minutes")

# ── Store filters in session state for pages ─────────────────────────────────
st.session_state["filter_start"] = start_date.strftime("%Y-%m-%d")
st.session_state["filter_end"] = end_date.strftime("%Y-%m-%d")
st.session_state["filter_services"] = selected_services

# ── Main landing page ────────────────────────────────────────────────────────
st.title("Cortex AI Cost Dashboard")
st.markdown(
    """
    Welcome to the **Cortex AI Cost Dashboard**. Use the sidebar to set date
    ranges and filter services, then navigate to the pages below.

    | Page | Description |
    |---|---|
    | **Executive Summary** | Total credits, daily trend, MoM growth, projected spend |
    | **Service Breakdown** | Per-service deep dive across all Cortex services |
    | **Model Analysis** | Credits by model, cost-per-1K-tokens, token efficiency |
    | **Top Users & Roles** | Per-user and per-role cost attribution |
    | **Expensive Queries** | Top queries by credit cost with full details |
    | **Anomalies** | Spending spikes, runaway queries, idle Search services |
    | **Cortex Agents** | Per-agent costs, tool usage, agent tags |
    """
)

st.info(
    "This dashboard requires a role with access to **SNOWFLAKE.ACCOUNT_USAGE** "
    "(typically ACCOUNTADMIN or a role with the IMPORTED PRIVILEGES grant on the SNOWFLAKE database)."
)
