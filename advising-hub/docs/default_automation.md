# Default Automation / True Auto Rate — canonical calculation (reference)

**Purpose:** the source-of-truth for how a renewal is flagged as **default automation** ("true auto rate"). Use this instead of `REASON_FOR_ADVISING` (not reliable) and instead of the hub's old broken join. Companion SQL: `Default_Automation_true_auto_rate.sql`.

---

## The definition

A renewal is **auto-finalized (true default automation)** if a row exists for its renewal in **`HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS`**:

```sql
left join hawaiian_ice_production_no_pii.renewal_auto_finalize_records afr
  on afr.renewal_id = renewals.id      -- << join on hippo renewals.id
, case when afr.id is not null then 1 else 0 end as auto_finalize_success_flag
```

That table has only `id, renewal_id, created_at, updated_at` — **no status column**, so "row exists" is the only success signal. `renewal_true_auto_rate = count(afr row) / count(all renewals)`.

## Three buckets (what the query actually produces)

1. **Auto-finalized (true automation)** — `afr` row exists. Least advisor attention needed.
2. **Automation-eligible, not finalized** — passes eligibility (below) but no `afr` row. Should have automated; watch these.
3. **Not eligible** — fails eligibility → advisor must work it.

**Eligibility** (`eligible_renewal_flag`) = standard medical carrier (in `plan_recommendation_engine_new_relationship_supporte`, `new_relationship_supported=true`) **AND** not composite-rated (`medical_package_offerings.is_composite_rated=false`) **AND** ancillary is Guardian-only or none **AND** reached the `answering_survey_start__c` / `awaiting_offerings_start__c` stage **AND** within the 105-day pre-renewal window — OR an `afr` row already exists.

Rate-parsing success (`renewal_rate_parsing_records`, `successful=true` on all records → `success_rate=1`) is a diagnostic for why an eligible renewal did/didn't finalize.

## Cohort result (Jul–Dec 2026, 15,118 renewals)

| Metric | Value |
|---|---|
| Auto-finalized (true auto rate) | **7,194 (47.6%)** |
| Eligible | 10,635 (70%) |
| Success of eligible | 67.6% |

## ⚠️ The bug this replaces

The hub's `_renewal_full/sql/extras.sql` derived `default_automation` as `IFF(autofin.renewal_id IS NOT NULL,'Y','')` where `autofin = SELECT DISTINCT renewal_id FROM RENEWAL_AUTO_FINALIZE_RECORDS WHERE renewal_id IN (SELECT hi_renewal_id FROM o)`, joined `autofin.renewal_id = o.hi_renewal_id`. That linkage matched only **112 (0.7%)** — a broken/typed id join. The correct anchor is `renewals.id` (which equals `advising_opportunities.hi_renewal_id`), giving **47.6%**. Always validate the count is ~half, not <1%.

## Key source tables

- `HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS` — the auto-finalize flag (row exists).
- `HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWALS` (`.id`) — the join anchor; = `advising_opportunities.hi_renewal_id`.
- `HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_RATE_PARSING_RECORDS` — rate-parse success per renewal.
- `BI.POLICIES_HAWAIIAN_ICE` + `..._new_relationship_supporte` + `MEDICAL_PACKAGE_OFFERINGS` — eligibility (standard carrier, composite, Guardian ancillary).
- Reference docs: `HOWTO_Auto_Renewal_Definition.md`, `renewal_true_automation_drilldown.sql` (Drive). Note: canonical **customer auto-renewal** is a different metric — Snowplow `CATEGORY='Renewals' AND ACTION='ConfirmDefaultAndSkipFlow'` — do not conflate with default automation.
