# Auto-renewal — field definition (Advising Hub)

Plain-language definition of the **`auto_renewal`** field/signal as the hub uses it, and how it differs from **`default_automation`**. Both describe a renewal moving on its default plan with little or no advisor/customer action — but they are two different things and feed the risk model differently.

---

## What auto-renewal means

**`auto_renewal` = `Y`** marks a renewal opportunity that is set up to **renew into its current/default plan if the customer takes no action** — i.e. the customer is expected to be carried onto the successor (default) plan automatically rather than actively re-selecting. It is a *forward-looking* signal about how this opp will resolve, and it is the stated reason the opp is with advising. In the grid it shows as a single ● dot in the **Flags** group (`Auto-renewal`); the drill shows it as **Yes**.

## How it differs from default automation

- **Auto-renewal (`auto_renewal`)** — the renewal is *slated to* auto-renew onto the default plan (no active reselection expected). Forward-looking status.
- **Default automation (`default_automation`)** — the system **already auto-finalized** the default recommendation for this renewal: a row exists in `HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS` for the renewal (see `default_automation.md`). Backward-looking fact that the automated finalize *happened*.

A renewal can be auto-renewing without the system having auto-finalized it, and vice-versa. They are surfaced as two separate flags (`Auto-renewal`, `Default automation`) and never conflated.

## Source

- **`default_automation`** — derived in `queries/extras.sql`: `IFF(autofin.renewal_id IS NOT NULL,'Y','')`, where `autofin = SELECT DISTINCT renewal_id FROM HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS`. (Canonical join anchor / the ~48% "true auto rate": see `default_automation.md`.)
- **`auto_renewal`** — an open-signal flag carried per-opp from the prior published dataset (listed under `catalog.json → carry_forward_not_reconstructed`); it is not currently re-derived by a saved query in the daily merge path. The canonical customer auto-renewal event is the Snowplow action `CATEGORY='Renewals' AND ACTION='ConfirmDefaultAndSkipFlow'`.

## How each feeds risk

- **PF risk model** — `auto_renewal` is one of the five PF factors (weight **20** of 130). It only fires when `auto_renewal='Y'`, and its severity scales with the medical rate increase: `rate_increase_pct ≥20% → 1.0`, `≥14% → 0.6`, else `0.3`. The intent: a group being auto-renewed **into a material rate increase** without actively re-deciding is a retention risk ("auto-renewing into a X% increase"). When `auto_renewal` is not `Y`, the factor contributes 0.
- **Open risk model** — `auto_renewal` is **not** a direct signal (the Open model is pre-selection and reads advising-cycle signals instead). `default_automation` carries **weight 0** everywhere — it is informational only and never moves a score.
- **Closed** — risk is archived/frozen; the last PF-style score (including any auto-renewal contribution) is shown greyed.

---

*Companion to `default_automation.md`, `risk_profile.md`, and `data_dictionary.md`.*
