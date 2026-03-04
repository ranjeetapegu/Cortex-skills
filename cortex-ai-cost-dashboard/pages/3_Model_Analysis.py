import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from snowflake.snowpark.context import get_active_session
from datetime import datetime

session = get_active_session()

st.title("Model Analysis")

start = st.session_state.get("filter_start", "2024-01-01")
end = st.session_state.get("filter_end", datetime.today().strftime("%Y-%m-%d"))


@st.cache_data(ttl=600)
def get_model_credits(start_date, end_date):
    return session.sql(f"""
        SELECT
            MODEL_NAME,
            FUNCTION_NAME,
            SUM(CREDITS) AS TOTAL_CREDITS,
            COUNT(DISTINCT QUERY_ID) AS QUERY_COUNT
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND MODEL_NAME IS NOT NULL
          AND MODEL_NAME != ''
        GROUP BY 1, 2
        ORDER BY 3 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_model_tokens(start_date, end_date):
    """Get input/output token breakdown per model using METRICS column."""
    return session.sql(f"""
        SELECT
            MODEL_NAME,
            SUM(CREDITS) AS TOTAL_CREDITS,
            SUM(
                CASE
                    WHEN m.value:"key":"metric"::STRING = 'input'
                    THEN m.value:"value"::NUMBER ELSE 0
                END
            ) AS INPUT_TOKENS,
            SUM(
                CASE
                    WHEN m.value:"key":"metric"::STRING = 'output'
                    THEN m.value:"value"::NUMBER ELSE 0
                END
            ) AS OUTPUT_TOKENS,
            SUM(
                CASE
                    WHEN m.value:"key":"metric"::STRING = 'total'
                    THEN m.value:"value"::NUMBER ELSE 0
                END
            ) AS TOTAL_TOKENS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY,
            LATERAL FLATTEN(input => METRICS) m
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND MODEL_NAME IS NOT NULL
          AND MODEL_NAME != ''
        GROUP BY 1
        ORDER BY 2 DESC
    """).to_pandas()


@st.cache_data(ttl=600)
def get_model_daily_trend(start_date, end_date):
    return session.sql(f"""
        SELECT
            TO_DATE(START_TIME) AS USAGE_DATE,
            MODEL_NAME,
            SUM(CREDITS) AS CREDITS
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_FUNCTIONS_USAGE_HISTORY
        WHERE START_TIME BETWEEN '{start_date}' AND '{end_date}'
          AND MODEL_NAME IS NOT NULL
          AND MODEL_NAME != ''
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
    """).to_pandas()


# ── Credits by Model ──────────────────────────────────────────────────────────
st.subheader("Credits by Model")
model_credits_df = get_model_credits(start, end)

if not model_credits_df.empty:
    fig_model = px.treemap(
        model_credits_df,
        path=["MODEL_NAME", "FUNCTION_NAME"],
        values="TOTAL_CREDITS",
        color="TOTAL_CREDITS",
        color_continuous_scale="Blues",
    )
    fig_model.update_layout(height=450)
    st.plotly_chart(fig_model, use_container_width=True)

    col_chart, col_table = st.columns([1, 1])

    # Bar chart by model
    model_agg = model_credits_df.groupby("MODEL_NAME")["TOTAL_CREDITS"].sum().reset_index()
    model_agg = model_agg.sort_values("TOTAL_CREDITS", ascending=True)
    fig_bar = px.bar(model_agg, x="TOTAL_CREDITS", y="MODEL_NAME", orientation="h",
                     labels={"TOTAL_CREDITS": "Credits", "MODEL_NAME": "Model"})
    fig_bar.update_layout(height=400)
    col_chart.plotly_chart(fig_bar, use_container_width=True)

    col_table.dataframe(
        model_credits_df.sort_values("TOTAL_CREDITS", ascending=False).reset_index(drop=True),
        use_container_width=True,
    )
    col_table.download_button(
        "Download CSV",
        model_credits_df.to_csv(index=False),
        "model_credits.csv",
        "text/csv",
    )
else:
    st.info("No model usage data found for the selected period.")

st.markdown("---")

# ── Token Efficiency ──────────────────────────────────────────────────────────
st.subheader("Token Efficiency by Model")
token_df = get_model_tokens(start, end)

if not token_df.empty:
    # Calculate cost per 1K tokens
    token_df["COST_PER_1K_TOKENS"] = (
        token_df["TOTAL_CREDITS"] / (token_df["TOTAL_TOKENS"] / 1000)
    ).round(6)
    token_df["INPUT_OUTPUT_RATIO"] = (
        token_df["OUTPUT_TOKENS"] / token_df["INPUT_TOKENS"].replace(0, 1)
    ).round(2)

    k1, k2 = st.columns(2)

    # Cost per 1K tokens comparison
    cost_sorted = token_df[token_df["COST_PER_1K_TOKENS"].notna()].sort_values(
        "COST_PER_1K_TOKENS", ascending=True
    )
    if not cost_sorted.empty:
        fig_cost = px.bar(
            cost_sorted, x="COST_PER_1K_TOKENS", y="MODEL_NAME", orientation="h",
            labels={"COST_PER_1K_TOKENS": "Credits per 1K Tokens", "MODEL_NAME": "Model"},
            title="Cost per 1K Tokens",
        )
        fig_cost.update_layout(height=400)
        k1.plotly_chart(fig_cost, use_container_width=True)

    # Input vs Output tokens
    token_melt = token_df.melt(
        id_vars=["MODEL_NAME"],
        value_vars=["INPUT_TOKENS", "OUTPUT_TOKENS"],
        var_name="TOKEN_TYPE",
        value_name="TOKENS",
    )
    fig_tokens = px.bar(
        token_melt, x="TOKENS", y="MODEL_NAME", color="TOKEN_TYPE",
        orientation="h", barmode="group",
        labels={"TOKENS": "Token Count", "MODEL_NAME": "Model"},
        title="Input vs Output Tokens",
    )
    fig_tokens.update_layout(height=400, legend=dict(orientation="h", y=-0.15))
    k2.plotly_chart(fig_tokens, use_container_width=True)

    with st.expander("View token details"):
        st.dataframe(token_df, use_container_width=True)
        st.download_button(
            "Download Token CSV",
            token_df.to_csv(index=False),
            "model_tokens.csv",
            "text/csv",
        )
else:
    st.info("No token data found for the selected period.")

st.markdown("---")

# ── Daily Trend by Model ─────────────────────────────────────────────────────
st.subheader("Daily Credit Trend by Model")
trend_df = get_model_daily_trend(start, end)

if not trend_df.empty:
    fig_trend = px.area(
        trend_df, x="USAGE_DATE", y="CREDITS", color="MODEL_NAME",
        labels={"CREDITS": "Credits", "USAGE_DATE": "Date"},
    )
    fig_trend.update_layout(height=400, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No daily model trend data found.")
