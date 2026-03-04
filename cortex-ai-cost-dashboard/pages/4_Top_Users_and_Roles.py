import streamlit as st
import pandas as pd
import plotly.express as px
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Top Users & Roles")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))


@st.cache_data(ttl=600)
def get_top_users(start_date, end_date, limit=25):
    return session.sql(f"""
        SELECT
            u.NAME AS USER_NAME,
            u.EMAIL,
            u.DEFAULT_ROLE,
            SUM(h.CREDITS) AS TOTAL_CREDITS,
            COUNT(DISTINCT h.QUERY_ID) AS QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h
        JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS u
            ON h.USER_ID = u.USER_ID
        WHERE h.START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2, 3
        ORDER BY 4 DESC
        LIMIT {limit}
    """).to_pandas()


@st.cache_data(ttl=600)
def get_user_monthly_trend(start_date, end_date, limit=10):
    return session.sql(f"""
        WITH top_users AS (
            SELECT USER_ID, SUM(CREDITS) AS TOTAL
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
            WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT {limit}
        )
        SELECT
            DATE_TRUNC('MONTH', h.START_TIME)::DATE AS USAGE_MONTH,
            u.NAME AS USER_NAME,
            SUM(h.CREDITS) AS CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h
        JOIN top_users t ON h.USER_ID = t.USER_ID
        JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS u ON h.USER_ID = u.USER_ID
        WHERE h.START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_role_attribution(start_date, end_date):
    return session.sql(f"""
        SELECT
            r.value::STRING AS ROLE_NAME,
            SUM(h.CREDITS) AS TOTAL_CREDITS,
            COUNT(DISTINCT h.QUERY_ID) AS QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h,
            LATERAL FLATTEN(input => h.ROLE_NAMES) r
        WHERE h.START_TIME BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 30
    """).to_pandas()


@st.cache_data(ttl=600)
def get_user_model_breakdown(start_date, end_date, limit=10):
    return session.sql(f"""
        WITH top_users AS (
            SELECT USER_ID, SUM(CREDITS) AS TOTAL
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
            WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT {limit}
        )
        SELECT
            u.NAME AS USER_NAME,
            h.MODEL_NAME,
            SUM(h.CREDITS) AS CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY h
        JOIN top_users t ON h.USER_ID = t.USER_ID
        JOIN SNOWFLAKE.ACCOUNT_USAGE.USERS u ON h.USER_ID = u.USER_ID
        WHERE h.START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND h.MODEL_NAME IS NOT NULL AND h.MODEL_NAME != ''
        GROUP BY 1, 2
        ORDER BY 3 DESC
    """).to_pandas()


# ── Top Users ─────────────────────────────────────────────────────────────────
st.subheader("Top Users by Credit Consumption")
top_n = st.slider("Number of users to show", 5, 50, 25)
users_df = get_top_users(start, end, top_n)

if not users_df.empty:
    col_chart, col_table = st.columns([1, 1])

    fig_users = px.bar(
        users_df.sort_values("TOTAL_CREDITS", ascending=True).tail(20),
        x="TOTAL_CREDITS", y="USER_NAME", orientation="h",
        labels={"TOTAL_CREDITS": "Credits", "USER_NAME": "User"},
    )
    fig_users.update_layout(height=500)
    col_chart.plotly_chart(fig_users, use_container_width=True)

    col_table.dataframe(users_df.reset_index(drop=True), use_container_width=True)
    col_table.download_button(
        "Download Users CSV",
        users_df.to_csv(index=False),
        "top_users.csv",
        "text/csv",
    )
else:
    st.info("No user usage data found for the selected period.")

st.markdown("---")

# ── User Monthly Trend ────────────────────────────────────────────────────────
st.subheader("Monthly Trend - Top 10 Users")
user_trend_df = get_user_monthly_trend(start, end)

if not user_trend_df.empty:
    fig_trend = px.bar(
        user_trend_df, x="USAGE_MONTH", y="CREDITS", color="USER_NAME",
        barmode="stack",
        labels={"CREDITS": "Credits", "USAGE_MONTH": "Month"},
    )
    fig_trend.update_layout(height=400, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No monthly user trend data found.")

st.markdown("---")

# ── User-Model Breakdown ─────────────────────────────────────────────────────
st.subheader("Top Users by Model Choice")
user_model_df = get_user_model_breakdown(start, end)

if not user_model_df.empty:
    fig_um = px.bar(
        user_model_df, x="CREDITS", y="USER_NAME", color="MODEL_NAME",
        orientation="h", barmode="stack",
        labels={"CREDITS": "Credits", "USER_NAME": "User"},
    )
    fig_um.update_layout(height=450, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_um, use_container_width=True)
else:
    st.info("No user-model breakdown data found.")

st.markdown("---")

# ── Role Attribution ──────────────────────────────────────────────────────────
st.subheader("Cost Attribution by Role")
role_df = get_role_attribution(start, end)

if not role_df.empty:
    col_r1, col_r2 = st.columns([1, 1])

    fig_role = px.bar(
        role_df.sort_values("TOTAL_CREDITS", ascending=True).tail(20),
        x="TOTAL_CREDITS", y="ROLE_NAME", orientation="h",
        labels={"TOTAL_CREDITS": "Credits", "ROLE_NAME": "Role"},
    )
    fig_role.update_layout(height=500)
    col_r1.plotly_chart(fig_role, use_container_width=True)

    col_r2.dataframe(role_df.reset_index(drop=True), use_container_width=True)
    col_r2.download_button(
        "Download Roles CSV",
        role_df.to_csv(index=False),
        "role_attribution.csv",
        "text/csv",
    )
else:
    st.info("No role attribution data found for the selected period.")
