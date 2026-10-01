# Renewal Stage Gate — refresh pipeline (_rsg_pipeline)

Nightly, two-phase, mirrors the Advising Hub cadence.

## Phase A — Salesforce (4:00a ET, task `renewal-stage-gate-sf-pull`)
Claude (Salesforce MCP) pulls the in-scope cohort + related objects and writes:
- `sf_cache.json`  — { opps[], policies[], atts[], qaSheets[], recertTickets[] } in the record shape build_bundles.py expects (same shape as rsg_bundles.sample.json inputs).
- `sf_last_updated.json` — { pull_time, per-object MAX(SystemModstamp) }.
- `cohort.json` — { total, stages:[[name,n]], months:[[label,n]], novdec } from SOQL GROUP BY StageName and GROUP BY CALENDAR_YEAR/MONTH(Renewal_Date__c).
Scope: RecordType 'Benefits Renewal'; StageName in (Recommendation Sent, Engaged, Alternatives Requested, ER Confirm); Renewal_Date__c in the active Jul–Dec cohort window.

## Phase B — Snowflake + publish (8:30a ET, task `renewal-stage-gate-snowflake-publish`)
1. Fetch the 3A master list (Google Sheet "Medical" tab) → `scheme.txt`.
2. `python3 build_bundles.py` — extracts SNOW_A–F verbatim from renewal-gate-check-tool.html and runs them for EVERY opp in sf_cache.json (chunk ~150), assembling one bundle each. PAT read from ../snowflake_pat.env. Applies the reductions: 2A recert notes → classified verdict + controlled reason code (no raw note); 9A group address → "on file — verify in Hippo" flag. Writes `rsg_bundles.json`.
3. Capture Snowflake INFORMATION_SCHEMA last_altered for source tables → merge into cohort.json under `snow`.
4. `python3 build_final.py` — bakes the themed HTML (LF/BO-SLA theme, compact cohort strip, SF+Snowflake freshness panel, single-opp lookup with Opp link + Renewal ID + Hippo link) reading cohort.json for counts/freshness.
5. Publish: ShareSomething `update` at slug `renewal-stage-gating-check` (Gusto-internal, password-protected).

## Faithfulness rules
- Fetch SNOW_A–F and the SOQL verbatim from renewal-gate-check-tool.html — never rewrite the check logic.
- Only the data source changes (embedded, not live) and the 2A/9A displays are reduced to derived status.
- Verify: run the original render() over a few bundles in Node and diff verdicts vs the live tool (see build note).
