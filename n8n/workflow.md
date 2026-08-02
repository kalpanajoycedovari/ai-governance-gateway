# n8n workflow layout

1. Trigger
   - Schedule node (hourly) OR Webhook node that receives new agent traces.

2. Fetch traces
   - HTTP Request or Postgres node: pull traces not yet governed.

3. Loop
   - Split In Batches over the traces.

4. Govern (per trace)
   - HTTP Request node -> POST http://<backend>/govern with the trace JSON.

5. Branch on result
   - IF node on auto_pass:
       true  -> mark record as auto-approved.
       false -> route to a human: send the report to Slack or email,
                and write a "pending review" row.

6. Persist
   - Postgres node: insert the governance result (risk_level, findings, report,
     reviewer, timestamp) for the audit trail.

7. Optional weekly rollup
   - Schedule node -> aggregate pass rate, top failing articles, drift over time
     -> write a summary report. This is the artifact an auditor asks for.