Steps

- Step 1.
Clone/copy this folder and deploy to your account

- Step 2.
   Create the following db, schema, stage
  ```
    CREATE DATABASE IF NOT EXISTS CORTEX_COST_MONITOR;
    CREATE SCHEMA IF NOT EXISTS CORTEX_COST_MONITOR.DASHBOARD;
    CREATE STAGE IF NOT EXISTS CORTEX_COST_MONITOR.DASHBOARD.STREAMLIT_STAGE DIRECTORY=(ENABLE=TRUE);
  ```

- Step 3
 Upload python files in the snowflake stage and then you can create the streamlit using the follwing command 
   
```
    CREATE STREAMLIT CORTEX_COST_MONITOR.DASHBOARD.CORTEX_AI_COST_DASHBOARD
      ROOT_LOCATION = '@CORTEX_COST_MONITOR.DASHBOARD.STREAMLIT_STAGE'
      MAIN_FILE = 'streamlit_app.py'
      QUERY_WAREHOUSE = '<WAREHOUSE>'
      TITLE = 'Cortex AI Cost Dashboard';

    GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE <ROLE>;
```
 
 
