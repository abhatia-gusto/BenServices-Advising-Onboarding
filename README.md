# BenServices — Advising & Onboarding: canonical queries

Source-of-truth SQL behind the **Benefits Advising Performance** dashboard and the `advising-performance-dash-skill`. Private/internal (Gusto-managed). **No PII values, no credentials** — SQL definitions only.

## Layout
- `queries/` — one `.sql` per metric segment (12 total), run **verbatim**.
- `catalog.json` — index: segment → path → main table, joins, grain, params, dashboard metric.

## How consumers use this
The skill/dashboard fetches a segment's `.sql` from this repo (GitHub MCP `get_file_contents`), substitutes the date-window params, and runs it via the **Snowflake MCP** or the **`snow` CLI** (`GUSTIE_ADHOC_WH`, tz `America/Denver`). Each user brings their own GitHub + Snowflake access; this repo carries neither.

## Guardrail — canonical sources of truth
Run each query **verbatim**. Do not rewrite, restructure, reorder, change joins/filters/CTEs, or swap tables — even if it looks wrong. Changes are made **here** (commit → dashboards/skill pick it up), never by editing a copy at run time. You may freely enrich/join the **results** with other data; never edit the SQL.

## Window rule
For `opp_sla`, `bo_grain`, `ticket_sla`: run with a **wide start (e.g. 2024-01-01 to today) and bucket by close-month** — a month-only window drops opps that closed in-month but were created earlier and undercounts the tile.

## Attainment methodology (per-IC scorecard)
Per-metric attainment (cap 125): higher-is-better `min(actual/goal*100,125)`; lower-is-better `min(goal/actual*100,125)`.

| key | metric | area | goal | floor | dir |
|---|---|---|---|---|---|
| erConfirm | ER Confirm SLA | SLA | 70 | 45 | >= |
| rfd | RFD + Alt SLA | SLA | 60 | 45 | >= |
| tixSla | Ticket SLA | SLA | 65 | 50 | >= |
| availability | Phone Avail. | SLA | 80 | 65 | >= |
| abandon | Abandon (mod.) | SLA | 5 | 20 | <= |
| tixRate | Ticket Rate | Quality | 30 | 40 | <= |
| quality | Level AI QA | Quality | 90 | 80 | >= |

Area scores: SLA = avg(att of erConfirm, rfd, tixSla, availability, abandon); Quality = avg(att of tixRate, quality). **Avg Weighted** = (SLA*50%)+(Quality*50%). **QPR** = same but an area is zeroed if any of its metrics is below floor. Suggested rating: 1 = >=1 below floor; 3 = top 15% of no-floor pool by QPR; 2 = otherwise.

## Alt package check
"Alt sent" = an **alternate (non-default) package offering exists** in `bi.fct_health_insurance_renewal_recommendation` (`default_flag = false`; `recommended_flag` = DA recommended indicator). Not the stage transition, not an attached document.

Owner: Aman Bhatia.
