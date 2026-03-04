import streamlit as st
import pandas as pd
import plotly.express as px
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Cortex Agents")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))


@st.cache_data(ttl=600)
def get_agent_summary(start_date, end_date):
    return session.sql(f"""
        SELECT
            AGENT_NAME,
            AGENT_DATABASE_NAME,
            AGENT_SCHEMA_NAME,
            SUM(TOKEN_CREDITS) AS TOTAL_CREDITS,
            SUM(TOKENS) AS TOTAL_TOKENS,
            COUNT(DISTINCT REQUEST_ID) AS REQUEST_COUNT,
            COUNT(DISTINCT USER_NAME) AS UNIQUE_USERS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2, 3
        ORDER BY 4 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_agent_daily_trend(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(START_TIME) AS USAGE_DATE,
            AGENT_NAME,
            SUM(TOKEN_CREDITS) AS CREDITS,
            COUNT(DISTINCT REQUEST_ID) AS REQUESTS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_agent_users(start_date, end_date):
    return session.sql(f"""
        SELECT
            AGENT_NAME,
            USER_NAME,
            SUM(TOKEN_CREDITS) AS TOTAL_CREDITS,
            SUM(TOKENS) AS TOTAL_TOKENS,
            COUNT(DISTINCT REQUEST_ID) AS REQUESTS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 3 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_agent_tags(start_date, end_date):
    return session.sql(f"""
        SELECT
            AGENT_NAME,
            t.value::STRING AS TAG,
            SUM(TOKEN_CREDITS) AS CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY,
            LATERAL FLATTEN(input => AGENT_TAGS, OUTER => TRUE) t
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 3 DESC
        LIMIT 50
    """).to_pandas()


# ── KPIs ──────────────────────────────────────────────────────────────────────
agent_df = get_agent_summary(start, end)

if not agent_df.empty:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Agent Credits", f"{agent_df['TOTAL_CREDITS'].sum():,.4f}")
    k2.metric("Total Requests", f"{agent_df['REQUEST_COUNT'].sum():,.0f}")
    k3.metric("Unique Agents", f"{agent_df['AGENT_NAME'].nunique()}")
    k4.metric("Unique Users", f"{agent_df['UNIQUE_USERS'].sum():,.0f}")
else:
    st.info("No Cortex Agent usage data found for the selected period.")

st.markdown("---")

# ── Agent Summary ─────────────────────────────────────────────────────────────
st.subheader("Agent Cost Summary")
if not agent_df.empty:
    col_chart, col_table = st.columns([1, 1])

    fig_agents = px.bar(
        agent_df.sort_values("TOTAL_CREDITS", ascending=True),
        x="TOTAL_CREDITS", y="AGENT_NAME", orientation="h",
        color="AGENT_DATABASE_NAME",
        labels={"TOTAL_CREDITS": "Credits", "AGENT_NAME": "Agent"},
    )
    fig_agents.update_layout(height=max(300, len(agent_df) * 35))
    col_chart.plotly_chart(fig_agents, use_container_width=True)

    col_table.dataframe(agent_df.reset_index(drop=True), use_container_width=True)
    col_table.download_button(
        "Download Agents CSV",
        agent_df.to_csv(index=False),
        "agent_summary.csv",
        "text/csv",
    )

st.markdown("---")

# ── Daily Trend ───────────────────────────────────────────────────────────────
st.subheader("Daily Agent Usage Trend")
trend_df = get_agent_daily_trend(start, end)

if not trend_df.empty:
    fig_trend = px.area(
        trend_df, x="USAGE_DATE", y="CREDITS", color="AGENT_NAME",
        labels={"CREDITS": "Credits", "USAGE_DATE": "Date"},
    )
    fig_trend.update_layout(height=400, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No daily agent trend data found.")

st.markdown("---")

# ── Per-Agent User Breakdown ──────────────────────────────────────────────────
st.subheader("Agent Usage by User")
user_df = get_agent_users(start, end)

if not user_df.empty:
    fig_users = px.treemap(
        user_df,
        path=["AGENT_NAME", "USER_NAME"],
        values="TOTAL_CREDITS",
        color="TOTAL_CREDITS",
        color_continuous_scale="Blues",
    )
    fig_users.update_layout(height=450)
    st.plotly_chart(fig_users, use_container_width=True)

    with st.expander("View details"):
        st.dataframe(user_df, use_container_width=True)
else:
    st.info("No agent-user data found.")

st.markdown("---")

# ── Agent Tags ────────────────────────────────────────────────────────────────
st.subheader("Agent Tags")
tags_df = get_agent_tags(start, end)

if not tags_df.empty:
    fig_tags = px.bar(
        tags_df, x="CREDITS", y="TAG", color="AGENT_NAME",
        orientation="h",
        labels={"CREDITS": "Credits", "TAG": "Tag"},
    )
    fig_tags.update_layout(height=max(300, len(tags_df) * 25))
    st.plotly_chart(fig_tags, use_container_width=True)

    with st.expander("View tag details"):
        st.dataframe(tags_df, use_container_width=True)
else:
    st.info("No agent tag data found.")
