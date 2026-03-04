import streamlit as st
import pandas as pd
import plotly.express as px
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Expensive Queries")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))


@st.cache_data(ttl=600)
def get_expensive_queries(start_date, end_date, limit=50):
    return session.sql(f"""
        SELECT
            h.QUERY_ID,
            h.FUNCTION_NAME,
            h.MODEL_NAME,
            h.CREDITS,
            q.USER_NAME,
            q.WAREHOUSE_NAME,
            q.START_TIME,
            q.EXECUTION_TIME / 1000 AS EXECUTION_SECONDS,
            LEFT(q.QUERY_TEXT, 500) AS QUERY_TEXT_PREVIEW,
            q.QUERY_TAG
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h
        JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
            ON h.QUERY_ID = q.QUERY_ID
        WHERE h.START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND h.CREDITS > 0
        ORDER BY h.CREDITS DESC
        LIMIT {limit}
    """).to_pandas()


@st.cache_data(ttl=600)
def get_credit_distribution(start_date, end_date):
    return session.sql(f"""
        SELECT
            CASE
                WHEN CREDITS < 0.001 THEN '< 0.001'
                WHEN CREDITS < 0.01 THEN '0.001 - 0.01'
                WHEN CREDITS < 0.1 THEN '0.01 - 0.1'
                WHEN CREDITS < 1 THEN '0.1 - 1.0'
                WHEN CREDITS < 10 THEN '1.0 - 10'
                ELSE '10+'
            END AS CREDIT_BUCKET,
            COUNT(*) AS QUERY_COUNT,
            SUM(CREDITS) AS TOTAL_CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND CREDITS > 0
        GROUP BY 1
        ORDER BY MIN(CREDITS)
    """).to_pandas()


@st.cache_data(ttl=600)
def get_long_running_queries(start_date, end_date, limit=20):
    return session.sql(f"""
        SELECT
            h.QUERY_ID,
            h.FUNCTION_NAME,
            h.MODEL_NAME,
            h.CREDITS,
            q.USER_NAME,
            q.EXECUTION_TIME / 1000 AS EXECUTION_SECONDS,
            LEFT(q.QUERY_TEXT, 300) AS QUERY_TEXT_PREVIEW,
            q.START_TIME
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h
        JOIN SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY q
            ON h.QUERY_ID = q.QUERY_ID
        WHERE h.START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND h.IS_COMPLETED = TRUE
        ORDER BY q.EXECUTION_TIME DESC
        LIMIT {limit}
    """).to_pandas()


# ── KPI ───────────────────────────────────────────────────────────────────────
dist_df = get_credit_distribution(start, end)
if not dist_df.empty:
    total_queries = dist_df["QUERY_COUNT"].sum()
    total_credits = dist_df["TOTAL_CREDITS"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Total AI Queries", f"{total_queries:,.0f}")
    k2.metric("Total Credits", f"{total_credits:,.4f}")
    k3.metric("Avg Credit / Query", f"{total_credits / total_queries:,.6f}" if total_queries > 0 else "N/A")

st.markdown("---")

# ── Credit Distribution ───────────────────────────────────────────────────────
st.subheader("Query Credit Distribution")
if not dist_df.empty:
    col1, col2 = st.columns(2)

    fig_count = px.bar(
        dist_df, x="CREDIT_BUCKET", y="QUERY_COUNT",
        labels={"CREDIT_BUCKET": "Credit Range", "QUERY_COUNT": "Query Count"},
        title="Query Count by Credit Bucket",
    )
    fig_count.update_layout(height=350)
    col1.plotly_chart(fig_count, use_container_width=True)

    fig_credits = px.bar(
        dist_df, x="CREDIT_BUCKET", y="TOTAL_CREDITS",
        labels={"CREDIT_BUCKET": "Credit Range", "TOTAL_CREDITS": "Total Credits"},
        title="Total Credits by Bucket",
    )
    fig_credits.update_layout(height=350)
    col2.plotly_chart(fig_credits, use_container_width=True)
else:
    st.info("No query distribution data found.")

st.markdown("---")

# ── Top Expensive Queries ─────────────────────────────────────────────────────
st.subheader("Most Expensive Queries")
top_n = st.slider("Number of queries", 10, 100, 50, key="exp_slider")
expensive_df = get_expensive_queries(start, end, top_n)

if not expensive_df.empty:
    # Summary bar
    fig_exp = px.bar(
        expensive_df.head(20),
        x="CREDITS", y="QUERY_ID", orientation="h",
        color="MODEL_NAME",
        hover_data=["USER_NAME", "FUNCTION_NAME", "EXECUTION_SECONDS"],
        labels={"CREDITS": "Credits", "QUERY_ID": "Query ID"},
        title="Top 20 by Credits",
    )
    fig_exp.update_layout(height=500)
    st.plotly_chart(fig_exp, use_container_width=True)

    # Full table
    st.dataframe(
        expensive_df,
        use_container_width=True,
        column_config={
            "QUERY_TEXT_PREVIEW": st.column_config.TextColumn("Query Text", width="large"),
        },
    )
    st.download_button(
        "Download Expensive Queries CSV",
        expensive_df.to_csv(index=False),
        "expensive_queries.csv",
        "text/csv",
    )
else:
    st.info("No expensive query data found for the selected period.")

st.markdown("---")

# ── Long Running Queries ──────────────────────────────────────────────────────
st.subheader("Longest Running AI Queries")
long_df = get_long_running_queries(start, end)

if not long_df.empty:
    fig_long = px.scatter(
        long_df, x="EXECUTION_SECONDS", y="CREDITS",
        size="CREDITS", color="MODEL_NAME",
        hover_data=["USER_NAME", "FUNCTION_NAME", "QUERY_ID"],
        labels={"EXECUTION_SECONDS": "Duration (seconds)", "CREDITS": "Credits"},
    )
    fig_long.update_layout(height=400)
    st.plotly_chart(fig_long, use_container_width=True)

    with st.expander("View details"):
        st.dataframe(long_df, use_container_width=True)
else:
    st.info("No long-running query data found.")
