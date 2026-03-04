import streamlit as st
import pandas as pd
import plotly.express as px
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Service Breakdown")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))
selected_services = st.session_state.get("filter_services", [])


@st.cache_data(ttl=600)
def get_ai_functions_daily(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(START_TIME) AS USAGE_DATE,
            FUNCTION_NAME,
            MODEL_NAME,
            SUM(CREDITS) AS CREDITS,
            COUNT(DISTINCT QUERY_ID) AS QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2, 3
        ORDER BY 1 DESC, 4 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_analyst_daily(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(START_TIME) AS USAGE_DATE,
            USERNAME,
            SUM(CREDITS) AS CREDITS,
            SUM(REQUEST_COUNT) AS MESSAGES
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 1 DESC, 3 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_agents_daily(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(START_TIME) AS USAGE_DATE,
            AGENT_NAME,
            SUM(TOKEN_CREDITS) AS CREDITS,
            SUM(TOKENS) AS TOKENS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 1 DESC, 3 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_search_daily(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(USAGE_DATE) AS USAGE_DATE,
            SERVICE_NAME,
            CONSUMPTION_TYPE,
            SUM(CREDITS) AS CREDITS,
            SUM(TOKENS) AS TOKENS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
        WHERE USAGE_DATE BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2, 3
        ORDER BY 1 DESC, 4 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_doc_processing_daily(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(START_TIME) AS USAGE_DATE,
            FUNCTION_NAME,
            MODEL_NAME,
            SUM(CREDITS_USED) AS CREDITS,
            SUM(PAGE_COUNT) AS PAGES_PROCESSED,
            SUM(DOCUMENT_COUNT) AS DOCS_PROCESSED
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2, 3
        ORDER BY 1 DESC, 4 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_code_cli_daily(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(USAGE_TIME) AS USAGE_DATE,
            SUM(TOKEN_CREDITS) AS CREDITS,
            SUM(TOKENS) AS TOKENS,
            COUNT(DISTINCT REQUEST_ID) AS REQUESTS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
        WHERE USAGE_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1
        ORDER BY 1 DESC
    """).to_pandas()


def render_service_section(title, df, date_col="USAGE_DATE", credit_col="CREDITS", color_col=None):
    """Render a standard service section with trend chart and table."""
    st.subheader(title)
    if df is None or df.empty:
        st.info(f"No {title} data found for the selected period.")
        return

    total = df[credit_col].sum()
    st.metric(f"Total Credits", f"{total:,.4f}")

    if color_col and color_col in df.columns:
        fig = px.bar(df, x=date_col, y=credit_col, color=color_col,
                     barmode="stack", labels={credit_col: "Credits", date_col: "Date"})
    else:
        fig = px.bar(df, x=date_col, y=credit_col,
                     labels={credit_col: "Credits", date_col: "Date"})
    fig.update_layout(height=350, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("View raw data"):
        st.dataframe(df, use_container_width=True)
        st.download_button(
            f"Download {title} CSV",
            df.to_csv(index=False),
            f"{title.lower().replace(' ', '_')}.csv",
            "text/csv",
        )


# ── AI Functions ──────────────────────────────────────────────────────────────
if "AI Functions" in selected_services:
    ai_df = get_ai_functions_daily(start, end)
    render_service_section("AI Functions", ai_df, color_col="FUNCTION_NAME")

# ── Cortex Analyst ────────────────────────────────────────────────────────────
if "Cortex Analyst" in selected_services:
    analyst_df = get_analyst_daily(start, end)
    render_service_section("Cortex Analyst", analyst_df, color_col="USERNAME")

# ── Cortex Agents ─────────────────────────────────────────────────────────────
if "Cortex Agents" in selected_services:
    agents_df = get_agents_daily(start, end)
    render_service_section("Cortex Agents", agents_df, color_col="AGENT_NAME")

# ── Cortex Search ─────────────────────────────────────────────────────────────
if "Cortex Search" in selected_services:
    search_df = get_search_daily(start, end)
    render_service_section("Cortex Search", search_df, color_col="CONSUMPTION_TYPE")

# ── Document Processing ───────────────────────────────────────────────────────
if "Document Processing" in selected_services:
    doc_df = get_doc_processing_daily(start, end)
    render_service_section("Document Processing", doc_df, color_col="FUNCTION_NAME")

# ── Cortex Code CLI ───────────────────────────────────────────────────────────
if "Cortex Code CLI" in selected_services:
    cli_df = get_code_cli_daily(start, end)
    render_service_section("Cortex Code CLI", cli_df)
