# Auto-renewal — field definition (Advising Hub)

Plain-language definition of the **`auto_renewal`** field/signal as the hub uses it, and how it differs from **`default_automation`**. Both touch a renewal's *default* plan, but they are two different things and feed the risk model differently.

---

## What auto-renewal means

**`auto_renewal` = `Y`** marks a renewal opportunity where the **customer confirmed the default package and skipped the renewal flow** — i.e. the customer actively accepted the default and opted out of the guided re-selection experience. It is a *customer action*, captured from Snowplow, and is the canonical customer auto-renewal signal. In the grid it shows as a single ● dot in the **Flags** group (`Auto-renewal`); the drill shows it as **Yes** (with the event date when available).

## How it differs from default automation

- **Auto-renewal (`auto_renewal`)** — the **customer** confirmed the default and skipped the flow (a customer-side action, from Snowplow).
- **Default automation (`default_automation`)** — the **system** auto-finalized the default recommendation for this renewal: a row exists in `HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS` for the renewal (see `default_automation.md`). A back-office/system fact, not a customer action.

A renewal can be auto-renewing (customer confirm-skip) without the system having auto-finalized it, and vice-versa. They are surfaced as two separate flags (`Auto-renewal`, `Default automation`) and never conflated.

## Source

- **`auto_renewal`** — derived in `queries/auto_renewal.sql` from `SNOWPLOW_FACTS.GA_TRACK_365_DAYS`: the event `CATEGORY='Renewals' AND ACTION='ConfirmDefaultAndSkipFlow'`, keyed `COMPANY_ID = advising_opportunities.zp_company_id`, restricted to this renewal's window `[renewal_date-120d, renewal_date+31d)` (companies renew annually, so the window keys the event to this cohort's opp). `auto_renewal='Y'` if >=1 in-window event fired, else `'N'`; `auto_renewal_date` = MIN in-window event date. This **replaced the old `ADVISING_OPPORTUNITIES.REASON_FOR_ADVISING ilike '%Auto-renewed%'` derivation**, which was unreliable and broke at FY26 Q2.
- **`default_automation`** — derived in `queries/extras.sql`: `IFF(autofin.renewal_id IS NOT NULL,'Y','')`, where `autofin = SELECT DISTINCT renewal_id FROM HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS`. (See `default_automation.md`.)

## How each feeds risk

- **PF risk model** — `auto_renewal` is one of the five PF factors (weight **20** of 130). It only fires when `auto_renewal='Y'`, and its severity scales with the medical rate increase: `rate_increase_pct >=20% -> 1.0`, `>=14% -> 0.6`, else `0.3`. The intent: a group that **confirmed the default and skipped into a material rate increase** without a guided re-decision is a retention risk ("auto-renewing into a X% increase"). When `auto_renewal` is not `Y`, the factor contributes 0.
- **Open risk model** — `auto_renewal` is **not** a direct signal (the Open model is pre-selection and reads advising-cycle signals instead). `default_automation` carries **weight 0** everywhere — informational only, never moves a score.
- **Closed** — risk is archived/frozen; the last PF-style score (including any auto-renewal contribution) is shown greyed.

---

*Companion to `default_automation.md`, `risk_profile.md`, and `data_dictionary.md`.*
