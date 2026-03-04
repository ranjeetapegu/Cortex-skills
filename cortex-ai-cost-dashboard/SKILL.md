---
name: cortex-ai-cost-dashboard
description: Deploy a multi-page Streamlit-in-Snowflake dashboard for monitoring and auditing Cortex AI costs across all services, models, users, and roles.
tools:
  - snowflake_sql_execute
  - bash
  - ask_user_question
---

# Cortex AI Cost Dashboard

Deploy a comprehensive multi-page Streamlit dashboard to Snowflake for monitoring, auditing, and governing Cortex AI costs. Covers AI Functions, Cortex Analyst, Cortex Agents, Cortex Search, Document Processing, Cortex Code CLI, and Fine-Tuning.

## When to Use

- User wants to monitor or audit Cortex AI costs
- User asks about AI credit consumption, spending, or billing
- User mentions "AI cost dashboard", "cortex cost", "AI usage", "cortex spend", "AI audit"
- User wants to track top AI users, model costs, or service breakdown
- User wants to deploy a cost monitoring Streamlit app

## Step 1: Gather User Inputs

Ask the user for the following using `ask_user_question`. Use sensible defaults shown in brackets:

1. **Database** — Snowflake database for the Streamlit app [default: `CORTEX_COST_MONITOR`]
2. **Schema** — Schema name [default: `DASHBOARD`]
3. **Warehouse** — Query warehouse for the Streamlit app [default: `COMPUTE_WH`]
4. **App name** — Streamlit object name [default: `CORTEX_AI_COST_DASHBOARD`]
5. **Grant access?** — Optional: grant access to additional roles [default: No]

If yes to grant access, also ask:
6. **Role names** — Comma-separated list of roles to grant USAGE on the Streamlit app

Present these as a single question with defaults clearly shown. Example prompt:

> I'll deploy the Cortex AI Cost Dashboard to your Snowflake account. Please confirm or adjust:
> - **Database**: `CORTEX_COST_MONITOR`
> - **Schema**: `DASHBOARD`
> - **Warehouse**: `COMPUTE_WH`
> - **App name**: `CORTEX_AI_COST_DASHBOARD`
> - **Grant to other roles?**: No
>
> **Note**: The deploying role needs access to `SNOWFLAKE.ACCOUNT_USAGE` views (typically ACCOUNTADMIN or a role with IMPORTED PRIVILEGES on the SNOWFLAKE database).

If the user only says "deploy", use all defaults.

## Step 2: Create Snowflake Objects

Run the following SQL statements using `snowflake_sql_execute`.

### Create database, schema, and stage

```sql
CREATE DATABASE IF NOT EXISTS <DATABASE>;
```

```sql
CREATE SCHEMA IF NOT EXISTS <DATABASE>.<SCHEMA>;
```

```sql
CREATE STAGE IF NOT EXISTS <DATABASE>.<SCHEMA>.STREAMLIT_STAGE
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'Stage for Cortex AI Cost Dashboard Streamlit app';
```

## Step 3: Upload Application Files

Use `bash` with `snow stage copy` to upload each file. The source files are located in the skill directory at `cortex-ai-cost-dashboard/`.

### Upload main entrypoint
```bash
snow stage copy cortex-ai-cost-dashboard/streamlit_app.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE --connection <active_connection> --overwrite
```

### Upload environment file
```bash
snow stage copy cortex-ai-cost-dashboard/environment.yml @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE --connection <active_connection> --overwrite
```

### Upload page files
```bash
snow stage copy cortex-ai-cost-dashboard/pages/1_Executive_Summary.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
snow stage copy cortex-ai-cost-dashboard/pages/2_Service_Breakdown.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
snow stage copy cortex-ai-cost-dashboard/pages/3_Model_Analysis.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
snow stage copy cortex-ai-cost-dashboard/pages/4_Top_Users_and_Roles.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
snow stage copy cortex-ai-cost-dashboard/pages/5_Expensive_Queries.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
snow stage copy cortex-ai-cost-dashboard/pages/6_Anomalies.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
snow stage copy cortex-ai-cost-dashboard/pages/7_Cortex_Agents.py @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE/pages/ --connection <active_connection> --overwrite
```

After upload, verify files are staged:
```bash
snow sql -q "LIST @<DATABASE>.<SCHEMA>.STREAMLIT_STAGE" --connection <active_connection>
```

## Step 4: Create the Streamlit App

```sql
CREATE OR REPLACE STREAMLIT <DATABASE>.<SCHEMA>.<APP_NAME>
  ROOT_LOCATION = '@<DATABASE>.<SCHEMA>.STREAMLIT_STAGE'
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = '<WAREHOUSE>'
  TITLE = 'Cortex AI Cost Dashboard'
  COMMENT = 'Multi-page dashboard for monitoring and auditing Cortex AI costs';
```

## Step 5: Grant Access (Optional)

If the user wants to share the dashboard with other roles:

```sql
GRANT USAGE ON DATABASE <DATABASE> TO ROLE <ROLE_NAME>;
GRANT USAGE ON SCHEMA <DATABASE>.<SCHEMA> TO ROLE <ROLE_NAME>;
GRANT USAGE ON STREAMLIT <DATABASE>.<SCHEMA>.<APP_NAME> TO ROLE <ROLE_NAME>;
```

**Important**: The viewing role also needs access to `SNOWFLAKE.ACCOUNT_USAGE`. Without it, all queries in the dashboard will fail. Grant this with:

```sql
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <ROLE_NAME>;
```

## Step 6: Report Results

After deployment, show the user:

1. **App URL**: `https://app.snowflake.com/<org>/<account>/#/streamlit-apps/<DATABASE>.<SCHEMA>.<APP_NAME>`
2. **Dashboard pages available**:
   - Executive Summary — Total credits, daily trend, MoM growth, projected spend
   - Service Breakdown — Per-service deep dive (AI Functions, Analyst, Agents, Search, Doc Processing, Code CLI)
   - Model Analysis — Credits by model, cost-per-1K-tokens, token efficiency
   - Top Users & Roles — Per-user and per-role cost attribution
   - Expensive Queries — Top queries by credit cost with full details
   - Anomalies — Spending spikes, runaway queries, idle Search services
   - Cortex Agents — Per-agent costs, tool usage, agent tags
3. **Required permissions**: Role must have access to SNOWFLAKE.ACCOUNT_USAGE

Tell the user they can open the app in Snowsight by navigating to **Streamlit** in the left sidebar.

## Dashboard Pages Reference

### Executive Summary
- KPIs: total credits, current month, MoM growth, projected month-end
- Daily credit consumption stacked bar (AI_SERVICES + AI_INFERENCE)
- Service breakdown donut chart
- Data sources: `METERING_DAILY_HISTORY`, all Cortex usage views

### Service Breakdown
- Individual sections for each Cortex service with daily trends
- Per-service total credits, query counts
- Data sources: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY`, `CORTEX_ANALYST_USAGE_HISTORY`, `CORTEX_AGENT_USAGE_HISTORY`, `CORTEX_SEARCH_DAILY_USAGE_HISTORY`, `CORTEX_DOCUMENT_PROCESSING_USAGE_HISTORY`, `CORTEX_CODE_CLI_USAGE_HISTORY`

### Model Analysis
- Treemap of credits by model and function
- Cost-per-1K-tokens comparison bar chart
- Input vs output token breakdown
- Daily credit trend by model (area chart)
- Data source: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` (METRICS column)

### Top Users & Roles
- Top N users by credit consumption with email and default role
- Monthly user trend (stacked bar)
- User-model choice breakdown
- Role attribution via ROLE_NAMES column
- Data sources: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` joined with `USERS`

### Expensive Queries
- Query credit distribution histogram
- Top N queries by credits with query text, user, warehouse
- Longest-running AI queries scatter plot (duration vs credits)
- Data sources: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` joined with `QUERY_HISTORY`

### Anomalies
- Anomaly detection: daily spend vs 7-day rolling average with 2-std-dev bound
- Day-over-day spike detection with configurable threshold
- Runaway queries exceeding credit threshold
- Idle Cortex Search services (serving credits without queries)
- Data sources: `METERING_DAILY_HISTORY`, `CORTEX_AI_FUNCTIONS_USAGE_HISTORY`, `CORTEX_SEARCH_DAILY_USAGE_HISTORY`

### Cortex Agents
- Agent summary: credits, requests, unique users per agent
- Daily agent usage trend (area chart)
- Agent-user treemap
- Agent tag breakdown
- Data source: `CORTEX_AGENT_USAGE_HISTORY`

## Error Handling

- If `CREATE STREAMLIT` fails, check that the warehouse exists and the role has CREATE STREAMLIT privileges
- If stage copy fails, verify the file paths and that the stage exists
- If the dashboard shows no data, the viewing role likely lacks SNOWFLAKE.ACCOUNT_USAGE access — suggest `GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <role>`
- If specific pages show errors, individual views may not exist in the account (e.g., `CORTEX_AGENT_USAGE_HISTORY` is relatively new) — the dashboard handles empty results gracefully with info messages

## Examples

### Example 1: Quick deploy with defaults
```
User: $cortex-ai-cost-dashboard
```
Uses defaults: CORTEX_COST_MONITOR.DASHBOARD, COMPUTE_WH, no role grants.

### Example 2: Custom deployment
```
User: $cortex-ai-cost-dashboard
```
User provides:
- Database: ANALYTICS
- Schema: AI_MONITORING
- Warehouse: ANALYTICS_WH
- App name: AI_COST_TRACKER
- Grant to: DATA_TEAM_RL, FINANCE_RL

### Example 3: Deploy and share
```
User: Deploy the AI cost dashboard and share it with the engineering team
```
Agent deploys with defaults and grants access to the specified role(s).
