# BenServices Advising & Onboarding — Data Infrastructure

Canonical source-of-truth SQL behind the Benefit Services dashboards. Each dashboard
is a top-level folder with a `queries/` directory (one `.sql` per segment) and a
`catalog.json` (segment id → path, family, grain, params, metrics). The Cowork skills
fetch these queries **live** at run time, so they work on any machine with the GitHub
MCP + Snowflake MCP/CLI.

| Dashboard | Folder | Skill | Scorecard? |
|---|---|---|---|
| Benefits Advising Performance | `advising-performance/` | `advising-performance-dash-skill` | yes (per-IC) |
| Broker Onboarding Performance (BYB + BT) | `broker-onboarding/` | `broker-onboarding-performance-dash-skill` | yes (per-IC) |
| New Plan & Renewal Onboarding Performance | `npr-onboarding/` | `npr-performance-dash-skill` | yes (per-IC) |
| Advising Net MRR Retention | `advising-mrr/` | `advising-mrr-dash-skill` | no (MRR by cohort/advisor) |

**Run:** warehouse `GUSTIE_ADHOC_WH`, timezone `America/Denver` (MT). Substitute each
segment's exact param placeholders (see the folder's `catalog.json`).

**Guardrail:** these queries are canonical dashboard definitions — run verbatim. Changing
one is a dashboard change (query → pipeline → repo → skill), owned by Aman. Enriching or
joining the *results* with other sources is encouraged; editing the SQL is not.

Owner: Aman Bhatia (aman.bhatia@gusto.com).
