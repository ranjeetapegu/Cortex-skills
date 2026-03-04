import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Anomalies & Alerts")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))


@st.cache_data(ttl=600)
def get_daily_spend_with_anomalies(start_date, end_date):
    return session.sql(f"""
        WITH daily AS (
            SELECT
                TO_DATE(USAGE_DATE) AS USAGE_DATE,
                SUM(CREDITS_USED) AS DAILY_CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE SERVICE_TYPE IN ('AI_SERVICES', 'AI_INFERENCE')
              AND USAGE_DATE BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY 1
        )
        SELECT
            USAGE_DATE,
            DAILY_CREDITS,
            AVG(DAILY_CREDITS) OVER (
                ORDER BY USAGE_DATE ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) AS ROLLING_7D_AVG,
            STDDEV(DAILY_CREDITS) OVER (
                ORDER BY USAGE_DATE ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) AS ROLLING_7D_STDDEV
        FROM daily
        ORDER BY USAGE_DATE
    """).to_pandas()


@st.cache_data(ttl=600)
def get_day_over_day_spikes(start_date, end_date):
    return session.sql(f"""
        WITH daily AS (
            SELECT
                TO_DATE(USAGE_DATE) AS USAGE_DATE,
                SUM(CREDITS_USED) AS DAILY_CREDITS
            FROM SNOWFLAKE.ACCOUNT_USAGE.METERING_DAILY_HISTORY
            WHERE SERVICE_TYPE IN ('AI_SERVICES', 'AI_INFERENCE')
              AND USAGE_DATE BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY 1
        )
        SELECT
            USAGE_DATE,
            DAILY_CREDITS,
            LAG(DAILY_CREDITS) OVER (ORDER BY USAGE_DATE) AS PREV_DAY_CREDITS,
            CASE
                WHEN LAG(DAILY_CREDITS) OVER (ORDER BY USAGE_DATE) > 0
                THEN ROUND((DAILY_CREDITS / LAG(DAILY_CREDITS) OVER (ORDER BY USAGE_DATE) - 1) * 100, 1)
                ELSE NULL
            END AS DOD_CHANGE_PCT
        FROM daily
        ORDER BY USAGE_DATE DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_idle_search_services(start_date, end_date):
    return session.sql(f"""
        SELECT
            DATABASE_NAME,
            SCHEMA_NAME,
            SERVICE_NAME,
            SUM(CASE WHEN CONSUMPTION_TYPE = 'serving' THEN CREDITS ELSE 0 END) AS SERVING_CREDITS,
            SUM(CASE WHEN CONSUMPTION_TYPE != 'serving' THEN CREDITS ELSE 0 END) AS OTHER_CREDITS,
            SUM(CREDITS) AS TOTAL_CREDITS,
            COUNT(DISTINCT USAGE_DATE) AS ACTIVE_DAYS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_SEARCH_DAILY_USAGE_HISTORY
        WHERE USAGE_DATE BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY 1, 2, 3
        ORDER BY SERVING_CREDITS DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_runaway_queries(start_date, end_date, credit_threshold=1.0):
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
          AND h.CREDITS >= {credit_threshold}
        ORDER BY h.CREDITS DESC
        LIMIT 25
    """).to_pandas()


# ── Anomaly Detection Chart ───────────────────────────────────────────────────
st.subheader("Daily Spend with Anomaly Detection")
anomaly_df = get_daily_spend_with_anomalies(start, end)

if not anomaly_df.empty:
    anomaly_df["UPPER_BOUND"] = anomaly_df["ROLLING_7D_AVG"] + 2 * anomaly_df["ROLLING_7D_STDDEV"].fillna(0)
    anomaly_df["IS_ANOMALY"] = anomaly_df["DAILY_CREDITS"] > anomaly_df["UPPER_BOUND"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=anomaly_df["USAGE_DATE"], y=anomaly_df["DAILY_CREDITS"],
        mode="lines+markers", name="Daily Credits",
        line=dict(color="steelblue"),
    ))
    fig.add_trace(go.Scatter(
        x=anomaly_df["USAGE_DATE"], y=anomaly_df["ROLLING_7D_AVG"],
        mode="lines", name="7-Day Rolling Avg",
        line=dict(color="gray", dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=anomaly_df["USAGE_DATE"], y=anomaly_df["UPPER_BOUND"],
        mode="lines", name="Upper Bound (2 Std Dev)",
        line=dict(color="orange", dash="dot"),
    ))

    # Highlight anomalies
    anomalies = anomaly_df[anomaly_df["IS_ANOMALY"]]
    if not anomalies.empty:
        fig.add_trace(go.Scatter(
            x=anomalies["USAGE_DATE"], y=anomalies["DAILY_CREDITS"],
            mode="markers", name="Anomaly",
            marker=dict(color="red", size=12, symbol="x"),
        ))

    fig.update_layout(
        height=450,
        legend=dict(orientation="h", y=-0.2),
        yaxis_title="Credits",
    )
    st.plotly_chart(fig, use_container_width=True)

    anomaly_count = anomalies.shape[0]
    if anomaly_count > 0:
        st.warning(f"Detected **{anomaly_count} anomalous day(s)** where spend exceeded 2 standard deviations above the 7-day rolling average.")
        with st.expander("View anomaly details"):
            st.dataframe(anomalies[["USAGE_DATE", "DAILY_CREDITS", "ROLLING_7D_AVG", "UPPER_BOUND"]], use_container_width=True)
    else:
        st.success("No spending anomalies detected in the selected period.")
else:
    st.info("No daily spending data found.")

st.markdown("---")

# ── Day-over-Day Spikes ──────────────────────────────────────────────────────
st.subheader("Day-over-Day Spending Changes")
spike_df = get_day_over_day_spikes(start, end)

if not spike_df.empty:
    spike_threshold = st.slider("Spike threshold (%)", 50, 500, 100, step=25, key="spike_thresh")
    significant = spike_df[spike_df["DOD_CHANGE_PCT"].notna() & (spike_df["DOD_CHANGE_PCT"].abs() >= spike_threshold)]

    if not significant.empty:
        fig_spike = px.bar(
            significant, x="USAGE_DATE", y="DOD_CHANGE_PCT",
            color=significant["DOD_CHANGE_PCT"].apply(lambda x: "Spike" if x > 0 else "Drop"),
            color_discrete_map={"Spike": "red", "Drop": "green"},
            labels={"DOD_CHANGE_PCT": "% Change", "USAGE_DATE": "Date"},
        )
        fig_spike.update_layout(height=350, showlegend=True)
        st.plotly_chart(fig_spike, use_container_width=True)

        st.dataframe(significant, use_container_width=True)
    else:
        st.success(f"No day-over-day changes exceeding {spike_threshold}% detected.")
else:
    st.info("No daily data for spike analysis.")

st.markdown("---")

# ── Runaway Queries ───────────────────────────────────────────────────────────
st.subheader("Runaway Queries (High Credit)")
credit_thresh = st.number_input("Credit threshold", min_value=0.1, value=1.0, step=0.5, key="runaway_thresh")
runaway_df = get_runaway_queries(start, end, credit_thresh)

if not runaway_df.empty:
    st.warning(f"Found **{len(runaway_df)} queries** consuming >= {credit_thresh} credits each.")
    st.dataframe(
        runaway_df,
        use_container_width=True,
        column_config={
            "QUERY_TEXT_PREVIEW": st.column_config.TextColumn("Query Text", width="large"),
        },
    )
    st.download_button(
        "Download Runaway Queries CSV",
        runaway_df.to_csv(index=False),
        "runaway_queries.csv",
        "text/csv",
    )
else:
    st.success(f"No queries found exceeding {credit_thresh} credits.")

st.markdown("---")

# ── Idle Search Services ──────────────────────────────────────────────────────
st.subheader("Cortex Search Services - Serving Cost")
search_df = get_idle_search_services(start, end)

if not search_df.empty:
    st.markdown(
        "Cortex Search charges **serving credits continuously**, even when idle. "
        "Review services with high serving costs but low query activity."
    )

    fig_search = px.bar(
        search_df, x="SERVICE_NAME", y=["SERVING_CREDITS", "OTHER_CREDITS"],
        barmode="stack",
        labels={"value": "Credits", "SERVICE_NAME": "Service"},
    )
    fig_search.update_layout(height=350, legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig_search, use_container_width=True)

    st.dataframe(search_df, use_container_width=True)
    st.download_button(
        "Download Search Services CSV",
        search_df.to_csv(index=False),
        "search_services.csv",
        "text/csv",
    )
else:
    st.info("No Cortex Search usage data found.")
