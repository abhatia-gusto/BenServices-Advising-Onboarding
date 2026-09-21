# 2026-09-20 — Premium redesign (clean successor-matched YoY)

## What & why
The premium change shown on the hub was wrong for Closed opps (blended `d_fin` from
`premium_lines_delta` produced churn/tiny-denominator garbage — e.g. +496%, and negative
reads on real increases from roster turnover), and blank for pre-selection Open/PF opps.
This adds a clean, Hippo-matching premium computation and rewires the display.

## Eval (new vs. dashboard-today, full cohort)
- Rate unchanged: new eligible rate == `rate_increase_pct` for ~100% of opps within 1pt (enrolled-weighted = EYO2).
- Closed fix: of 6,624 closed medical opps, 2,975 (45%) move >=10pts; 1,028 currently show a NEGATIVE change that is actually positive (churn-masked); worst current values were +496/+498/+408% artifacts -> now sane (~20-26%).
- Coverage: ~2,469 open/PF opps that were blank now show a projected premium.
- Reconciles to the Hippo renewal page to the cent (Bloom 12.8% eligible-member / 11.9% enrolled-weighted; Omniscient finalized +21.7%).

## New segment — `advising-hub/queries/premium_yoy.sql`
Per-opp medical. current = `expiring_policies.eligible_employee_cost_breakdown`, renewal =
`renewal_plan_recommendations.individual_cost_breakdown` (DEFAULT package), matched via
`effective_successor_plan_uuid` -> `benefits_plans.id`. Both eligible per-employee (so EE-only vs
with-dependents are apples-to-apples). ENROLLED-weighted (= EYO2). Emits `prem_ee_pct`,
`prem_dep_pct`, `prem_book_cur`, `prem_book_proj`, `prem_enr`, `prem_fin_elig_pct` (finalized,
from fct `selected_flag`). Non-critical (carry forward on pull failure).

## catalog.json — add entry (after the `rate_index` entry)
```json
    {"id":"premium_yoy","file":"premium_yoy.sql","grain":"opp","params":["cohort_dates"],"out_csv":"_renewal_vnext/out/premium_yoy.csv","feeds":["prem_ee_pct","prem_dep_pct","prem_book_cur/prem_book_proj","prem_enr","prem_fin_elig_pct (finalized selected, clean — replaces garbage d_fin for Closed)"],"_note":"CLEAN Hippo-matching premium change. current=expiring_policies.eligible_employee_cost_breakdown, renewal=renewal_plan_recommendations.individual_cost_breakdown (DEFAULT package), matched via effective_successor_plan_uuid->benefits_plans.id. Both eligible per-employee. Enrolled-weighted = EYO2. All Open/PF AND Closed (daily refresh, ungated — nothing frozen)."},
```

## refresh_advising_hub.py — two hunks (in merge_freeze)
**(1) after the `ratev = {...}` line:**
```python
    pyoy_failed = "premium_yoy" in failed
    pyoyv = {} if pyoy_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","premium_yoy.csv"))}
```
**(2) in the per-opp loop, right after the rate_index overlay block (`... l[\"rate_pct\"] = pct`), UNGATED so Closed refreshes daily too:**
```python
            if not pyoy_failed:                          # CLEAN Hippo-matching premium change (all opps, daily)
                py = pyoyv.get(oid)
                row["prem_ee_pct"]       = fnum(py.get("PREM_EE_PCT")) if py else None
                row["prem_dep_pct"]      = fnum(py.get("PREM_DEP_PCT")) if py else None
                row["prem_book_cur"]     = fnum(py.get("PREM_BOOK_CUR")) if py else None
                row["prem_book_proj"]    = fnum(py.get("PREM_BOOK_PROJ")) if py else None
                row["prem_enr"]          = int(fnum(py.get("PREM_ENR"))) if (py and py.get("PREM_ENR") not in (None,"")) else None
                row["prem_fin_elig_pct"] = fnum(py.get("PREM_FIN_ELIG_PCT")) if py else None
```

## build_advising_hub.py — display hunks (stop using garbage d_fin; show clean prem_* )
1. **Grid column sort** (`k:"rate"` column): closed uses `prem_fin_elig_pct` (fallback `prem_ee_pct`->`rate_increase_pct`); open/pf uses `prem_ee_pct`->`rate_increase_pct`.
2. **`rateCell(r)`**: same precedence — closed `prem_fin_elig_pct` else `proj`; open/pf `proj = prem_ee_pct ?? rate_increase_pct`.
3. **`drillPremium` medical `premDelta`**: closed `prem_fin_elig_pct ?? prem_ee_pct ?? rate_increase_pct`; open/pf `prem_ee_pct ?? rate_increase_pct` (was `closed ? l.d_fin : rate_increase_pct`).
4. **Premium & Lines section**: `premMedDelta` closed uses `prem_fin_elig_pct`; add rows `With dependents Δ` (`prem_dep_pct`), `Premium book (monthly)` (`prem_book_cur`->`prem_book_proj`), and (closed) `Projected (at close)` (retained `prem_ee_pct`); foot note reworded (clean per-employee sources, Hippo-matching; Closed: projected retained + 30-day maturation).

## Recurring / freeze
Wired ungated in merge_freeze -> prem_* refresh DAILY for every opp incl Closed via the existing
Phase B task. Nothing premium stays frozen; only Salesforce-sourced fields freeze on close (unchanged).
