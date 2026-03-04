import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Executive Summary")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))


@st.cache_data(ttl=600)
def get_daily_metering(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(USAGE_DATE) AS USAGE_DATE,
            SERVICE_TYPE,
            SUM(CREDITS_USED) AS CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
        WHERE SERVICE_TYPE IN ('AI_SERVICES', 'AI_INFERENCE')
          AND USAGE_DATE BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2
        ORDER BY 1
    """).to_pandas()


@st.cache_data(ttl=600)
def get_service_breakdown(start_date, end_date):
    return session.sql(f"""
        SELECT 'AI Functions' AS SERVICE, SUM(CREDITS) AS CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        UNION ALL
        SELECT 'Cortex Analyst', SUM(CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_ANALYST_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        UNION ALL
        SELECT 'Cortex Agents', SUM(TOKEN_CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        UNION ALL
        SELECT 'Cortex Search', SUM(CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
        WHERE USAGE_DATE BETWEEN '{start_date}' AND '{end_date}'
        UNION ALL
        SELECT 'Document Processing', SUM(CREDITS_USED)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
        UNION ALL
        SELECT 'Cortex Code CLI', SUM(TOKEN_CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
        WHERE USAGE_TIME BETWEEN '{start_date}' AND '{end_date}'
        UNION ALL
        SELECT 'Fine-Tuning', SUM(TOKEN_CREDITS)
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FINE_TUNING_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
    """).to_pandas()


@st.cache_data(ttl=600)
def get_mom_comparison(end_date):
    return session.sql(f"""
        WITH current_month AS (
            SELECT SUM(CREDITS_USED) AS CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE SERVICE_TYPE IN ('AI_SERVICES', 'AI_INFERENCE')
              AND USAGE_DATE >= DATE_TRUNC('MONTH', '{end_date}'::DATE)
              AND USAGE_DATE <= '{end_date}'
        ),
        previous_month AS (
            SELECT SUM(CREDITS_USED) AS CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE SERVICE_TYPE IN ('AI_SERVICES', 'AI_INFERENCE')
              AND USAGE_DATE >= DATEADD('MONTH', -1, DATE_TRUNC('MONTH', '{end_date}'::DATE))
              AND USAGE_DATE < DATE_TRUNC('MONTH', '{end_date}'::DATE)
        )
        SELECT
            COALESCE(c.CREDITS, 0) AS CURRENT_MONTH_CREDITS,
            COALESCE(p.CREDITS, 0) AS PREVIOUS_MONTH_CREDITS
        FROM current_month c, previous_month p
    """).to_pandas()


# ── Fetch data ────────────────────────────────────────────────────────────────
daily_df = get_daily_metering(start, end)
service_df = get_service_breakdown(start, end)
mom_df = get_mom_comparison(end)

# ── KPI Cards ─────────────────────────────────────────────────────────────────
total_credits = daily_df["CREDITS"].sum() if not daily_df.empty else 0
current_month = mom_df["CURRENT_MONTH_CREDITS"].iloc[0] if not mom_df.empty else 0
prev_month = mom_df["PREVIOUS_MONTH_CREDITS"].iloc[0] if not mom_df.empty else 0
mom_growth = ((current_month - prev_month) / prev_month * 100) if prev_month > 0 else 0

# Projected spend: current month credits / days elapsed * days in month
today = datetime.today()
days_elapsed = today.day
import calendar
days_in_month = calendar.monthrange(today.year, today.month)[1]
projected_spend = (current_month / days_elapsed * days_in_month) if days_elapsed > 0 else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Credits (Period)", f"{total_credits:,.2f}")
k2.metric("Current Month", f"{current_month:,.2f}")
k3.metric("MoM Growth", f"{mom_growth:+.1f}%",
          delta=f"{mom_growth:+.1f}%",
          delta_color="inverse")
k4.metric("Projected Month-End", f"{projected_spend:,.2f}")

st.markdown("---")

# ── Daily Trend ───────────────────────────────────────────────────────────────
st.subheader("Daily Credit Consumption")
if not daily_df.empty:
    fig_daily = px.bar(
        daily_df,
        x="USAGE_DATE",
        y="CREDITS",
        color="SERVICE_TYPE",
        barmode="stack",
        labels={"CREDITS": "Credits", "USAGE_DATE": "Date"},
    )
    fig_daily.update_layout(height=400, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_daily, use_container_width=True)
else:
    st.info("No metering data found for the selected period.")

# ── Service Breakdown Pie ─────────────────────────────────────────────────────
st.subheader("Credits by Cortex Service")
col_pie, col_table = st.columns([1, 1])

if not service_df.empty:
    svc_clean = service_df[service_df["CREDITS"].notna() & (service_df["CREDITS"] > 0)]
    if not svc_clean.empty:
        fig_pie = px.pie(
            svc_clean,
            values="CREDITS",
            names="SERVICE",
            hole=0.4,
        )
        fig_pie.update_layout(height=400)
        col_pie.plotly_chart(fig_pie, use_container_width=True)

        col_table.dataframe(
            svc_clean.sort_values("CREDITS", ascending=False).reset_index(drop=True),
            use_container_width=True,
        )
        col_table.download_button(
            "Download CSV",
            svc_clean.to_csv(index=False),
            "service_breakdown.csv",
            "text/csv",
        )
    else:
        st.info("No service usage data found for the selected period.")
else:
    st.info("No service usage data found for the selected period.")
