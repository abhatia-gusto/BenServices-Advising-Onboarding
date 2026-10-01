# common/ — shared Salesforce-CLI pull library

`sf_pull.py` and `sf_parity_check.py` back the SF-CLI data-access layer for the three
dashboards that pull live Salesforce fields (Advising Hub Phase A, Renewal Stage Gate
Phase A, LF pre-pull). They replace the Salesforce-MCP / in-subagent pulls — **only the
data source moves; no metric, definition, or classifier logic changes.**

`sf_pull.soql_all` / `fetch`:
- batch IN()-style queries by id (drivers own the verbatim SOQL);
- **assert `done==True`** on every result;
- **50K cap guard**: on `totalSize>50000`/`done==False`, auto-fall-back to `sf data export
  bulk` (Bulk API 2.0, no cap) or chunk the id-set, AND write `SF_50K_CAP_HIT.flag` + emit a
  loud `⚠️ 50K cap hit …` line the pipeline's Slack/DM relays (so Aman is told);
- pass long SOQL via a temp `--file` (arg-length safe); `assert_fresh_clock()` guard.

Auth: `sf_cli.sh` + `salesforce_auth.env` (refresh token; NEVER committed). See
`SALESFORCE_CLI_SETUP.md`.
