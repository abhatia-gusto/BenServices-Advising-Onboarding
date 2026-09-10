# Premium-change methodology — comparison (reference)

Three ways "premium change" gets computed across our tools, why they differ, and where the benchmark estimate comes from. Tested live on 6 customers (below).

---

## The three methods

### 1. Product-aligned billed method (your Redash query)
- **Old cost:** the **billed** employee premium — `HEALTH_SUBSCRIPTION_DETAILS.employee_cost_cents` on the employee's *active* subscription at expiration (a ledger value of what they're actually charged; string like "$645.65").
- **New cost:** the successor plan's per-employee **quote** — the `employee` key of `RENEWAL_PLAN_RECOMMENDATIONS.individual_cost_breakdown` for the successor plan in the **DEFAULT** medical package.
- **Match:** per employee (`employee_id`); old→new plan via `expiring_policies.effective_successor_plan_uuid` (99.8% populated).
- **Formula:** `SUM(new_employee_premium) / SUM(old_employee_premium) − 1` per renewal.
- **Scope:** employee portion only (dependents excluded both sides); medical.
- This is what the Hippo renewal page shows as "average employee premium / difference from last year."

### 2. Hub "Projected" / EYO 2 (`rate_increase_pct`)
- **Premium:** `average_eligible_employee_premium_cost_amount` from the renewal **fact tables** (a modeled per-eligible-employee rate, NOT billed).
- **Compare:** lifecycle **expiring** → **default-flagged** recommendation on the **successor** plan (`dim_health_insurance_plan.successor_benefits_plan_id`).
- **Weighting:** `SUM(ee·pn)/SUM(ee·op) − 1` — eligible premium weighted by **enrolled** headcount.
- **Scope:** medical only, one number. Fallback to a benchmark **estimate** when there's no successor/default match (see below).
- Hub grid **Open/PF "Premium Δ (Projected)"** = this. EYO 2 uses the identical method.

### 3. Hub "Final" (`d_fin`, Closed only)
- **Enrolled** expiring premium → **enrolled** finalized (selected) premium, from the lifecycle `expiring` vs `selected` stages. What the customer actually landed on (dependent-loaded). No equivalent in EYO 2.

---

## Side-by-side (6 customers, live)

| Customer | Your billed query | Hub Projected | Hub Final (enrolled) |
|---|---|---|---|
| AAPMOR | $2,969→$3,533 · **+19.0%** | +17.6% | −6.4% |
| Prospection US | $4,330→$5,279 · **+21.9%** | **+94.8%** | +8.0% |
| Bay Harbour UMC | $1,142→$1,337 · **+17.1%** | +14.9% | −34.7% |
| Chioco Design | $8,168→$9,419 · **+15.3%** | +15.5% | +23.8% |
| MILES EDWARDS | $506→$558 · **+10.3%** | +10.6% | — |
| Topcu | $7,184→$9,774 · **+36.0%** | +15.0% *(estimate)* | — |

Agree within ~2 pts on most; diverge hard on **Prospection** (billed +22% vs hub's menu-blended default +95%) and **Topcu** (billed +36% vs hub's benchmark estimate +15%).

---

## Why they differ

1. **Billed vs modeled cost.** Yours = billed ledger (`employee_cost_cents`); hub = `average_eligible_employee_premium` from fact tables. These differ per opp (Prospection old was $1,443/EE billed vs $799 eligible-avg).
2. **Per-person vs group average.** Yours matches each employee old→new by id, then sums; hub uses plan/tier averages weighted by headcount.
3. **Exact successor vs default menu.** Yours pins to the one successor plan via `effective_successor_plan_uuid`; hub averages all default-flagged rows (often several tiers/plans → a menu blend that can inflate, e.g. Prospection).
4. **Estimate fallback.** Hub substitutes a benchmark estimate when no successor/default match; yours only computes on a real pair.
5. **Employee-portion vs eligible/enrolled bases.** Yours is employee-portion billed throughout; hub Projected is eligible-avg, hub Final is enrolled (dependent-loaded).

**Bottom line:** your query is the per-opp-accurate, product-faithful number (billed, exact successor plan). Hub Projected is a scalable fact-table proxy — accurate on average across 15k opps but can drift on individual opps. To make the hub match the product per opp, re-base its premium to the billed/`effective_successor_plan_uuid` method.

---

## Where the benchmark estimate comes from (hub `rate_status = "estimate (...)"`)

When an opp can't compute a direct expiring→successor-default increase (no successor match, or no default package built), the hub/EYO 2 substitutes a **historical benchmark**:

- Build a population of matched **expiring → successor-default** pairs across renewals (trailing window), each with `inc = new_eligible_premium / old_eligible_premium − 1`.
- **Benchmark = MEDIAN(inc) for that opp's medical carrier × state**, requiring **≥ 8 comparable pairs** in the cell.
- If the carrier×state cell has < 8 pairs, fall back to the **national median** of all pairs.
- Applied only when the opp's own increase is null; the field is tagged `estimate` (vs `computed`).

**Example — Topcu** (expiring medical carrier **UnitedHealthcare / GA**): carrier×state median **≈13.4%** from **1,120** pairs (national median ≈12.4%). The hub shows +15.0% for Topcu — the same mechanism, computed on the build-time trailing window (so it lands a bit above the all-history 13.4%). The point: the estimate is a carrier/state-typical renewal increase, not Topcu's own — which is why the billed method (+36%, Topcu's actual successor pair) diverges.

Source: EYO 2 `advising-performance`/EYO `q_rates.sql` (`paired`→`bench`→`nat`→`EST` CTEs); hub carries the result as `rate_increase_pct` + `rate_status`.
