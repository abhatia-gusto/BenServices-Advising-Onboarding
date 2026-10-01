# LF opp classifier — worker instructions

You answer TWO questions for each opportunity, from its Salesforce text:
  Q1. Did Gusto make a **level-funded (LF) proposal** to the customer — and through which channel?
  Q2. If the group did **NOT** end up on level-funded (stayed fully insured / renewed FI / churned), **why**?

Salesforce MCP query tool: `mcp__8dd0f6fd-f33f-48bd-ada9-e38796f1a8c8__query` (SOQL).

## Gather all three channels
Notes and Opp feed are small — pull each in one call for all your ids. **Renewal-case emails carry huge
TextBody threads (a single 5-opp pull with bodies can be 200KB+), so NEVER select TextBody for many ids at
once — it blows the tool-result token budget. Pull emails in TWO passes:** first grab lightweight metadata
for every id, then fetch bodies only for the emails that matter, by message-Id, in tiny groups.
1. Notes:  `SELECT Id, Notes__c FROM Opportunity WHERE Id IN ('id1',...)`  ← all ids, one call
2. Opp feed (chatter + posts):  `SELECT ParentId, Type, Body FROM OpportunityFeed WHERE ParentId IN (...) AND Type IN ('TextPost','ContentPost') ORDER BY ParentId, CreatedDate`  ← all ids, one call
3. Renewal-case emails — TWO passes so long threads don't overflow:
   3a. **Metadata for ALL your ids in ONE call (no body):**  `SELECT Id, Parent.Opportunity__c oid, Incoming, Subject, MessageDate FROM EmailMessage WHERE Parent.Opportunity__c IN (...) AND Parent.RecordType.Name='Benefits Renewal Case' ORDER BY Parent.Opportunity__c, MessageDate`
   3b. **Then fetch TextBody only for the emails that matter — by message-Id, in small groups of ≤5 Ids at a time:**  `SELECT Id, TextBody FROM EmailMessage WHERE Id IN ('emailId1',... ≤5 ...)`. "Matter" = the customer-facing renewal / rate-offer emails (Subject mentions renewal, "lower rates", "favorable", a savings %) plus the latest ~2–3 messages per opp. If a ≤5-Id body group STILL overflows, split it smaller (even 1 Id). Only set `email_fallback=true` for an opp whose decisive body you genuinely could not read after splitting. Skip bodies of obvious templated/auto emails — the Subject from 3a is enough for those.

**The opp FEED is decisive.** Advisors often post the final disposition in one line (e.g. "Group doesn't
have a business location, stay with fully insured plans", "moving to external broker", "selected LF").
If a feed post states why the group stayed FI or what they chose, it OVERRIDES ambiguous notes. Always read it.

## Q1 — proposal_made (decide from content; do not over-call)
**Core test: proposal_made=true ONLY if there is evidence the LF offer was actually PRESENTED TO THE
EMPLOYER (rates/savings/options shown or sent to the customer). Internally preparing, quoting, or STAGING
an LF quote is NOT a proposal.** When in doubt, mark false.

true ONLY if an actual LF offer was presented to the employer:
  - notes: LF recs / a cost breakdown / alternatives **sent to or reviewed WITH the customer**, or a
    selection deadline set — i.e. the employer was shown the LF options;
  - email: a "Gusto Health Plan Renewal – X% lower rates" / "Favorable Renewal" email, or any email body
    presenting LF savings/options to the customer (capture the % and date);
  - an explicit advisor LF-decision tag ("Declined LF: ...", "LF accepted", "LF quoted and declined") —
    LF was demonstrably on the table with the employer;
  - a feed/chatter post clearly stating LF was **offered to / discussed with the employer**.

NOT a proposal (do NOT set proposal_made=true on these alone):
  - **the automated feed/chatter post "a Level Funded quote has been uploaded in Hippo for the Group …"**
    (and any variant about a quote being uploaded/staged/loaded in Hippo). This is a SYSTEM event marking
    the internal LF quote being staged — it does NOT mean anyone presented LF to the employer. It is how a
    group ENTERS the LF population, not evidence of an offer. Treat it as neutral/internal only.
  - internal-only prep: "LF quote uploaded/loaded/built", "LF packet uploaded but not sent yet",
    "working on a level-funded quote", quotes sitting in Hippo/RP with no customer-facing send;
  - intro / first-touch outreach: intro calls (incl. voicemails), "sending intro email", welcome calls;
  - templated lifecycle emails (intro, "renewal ready for review", "renewing benefit details",
    "auto-renewed", reminders, OE/onboarding), generic outreach, or a QA/intake checklist.

Rule of thumb: if the ONLY LF signal is the "uploaded in Hippo" post (or another internal quote-prep note)
and there is no note/email/feed showing the employer was shown LF, then proposal_made=false and (if the
renewal is still open) reason_code=in_flight.

When true, set:  proposal_channels ⊆ ["notes/call","email","chatter"] · proposal_date (YYYY-MM-DD, best estimate) · proposal_evidence (≤160-char quote of the customer-facing offer).
When false: proposal_channels [], proposal_date "", proposal_evidence "".

## Q2 — reason_code (why this outcome)
Pick ONE. **If the group stayed fully insured / renewed FI / churned, the reason MUST be a non-win code
explaining why** — never a win code.
  not_interested  · group not interested in LF / wants to stay SGHI (fully insured)
  no_low_savings  · LF quoted but little/no savings
  no_uhc_quote    · no UHC LF quote could be produced
  unresponsive    · LF offered, group never responded → auto/default renewal
  not_eligible    · ineligible for LF (no business location, participation, group size, remote/OOS, etc.)
  auto_renewed    · selection deadline passed → auto-renewed default FI plans
  brokered_away   · moving to an external broker / BoR away
  terminated_churn· terminated all benefits / company closed / ancillary-only
  other           · claims/deductible/timing/misc
  win_lf_switch   · selected LF, switching medical carrier to UHC   ← ONLY if they actually chose LF
  win_lf_same     · selected LF, same carrier (UHC→UHC)             ← ONLY if they actually chose LF
  in_flight       · still open, no decision yet
  not_logged      · genuinely no signal in any channel
Also: reason_detail (one concrete advisor-voice sentence, ideally citing the feed/notes), and
churn (bool) + churn_type ["terminated","brokered_away","ancillary_only","company_closed","none"].

Do NOT decide the win/loss OUTCOME itself (that comes from realized funding upstream) — only the reason,
proposal, and churn. evidence = a short verbatim quote (≤160 chars) backing the reason; confidence 0–1.

## Output
Write a single JSON object {15-char opp id -> {reason_code, reason_detail, proposal_made, proposal_channels,
proposal_date, proposal_evidence, churn, churn_type, evidence, confidence, email_fallback}} to the EXACT path
you are given (e.g. .../outputs/signal_enrich_part_NN.json). Every assigned id must be a key. `email_fallback`
is a bool: true only if you could NOT retrieve that opp's full email TextBody (Subject-only fallback), else
false (also false for opps with no renewal-case emails at all). Return a one-line summary
(count · % proposal_made · reason mix · email_fallback count). Do not write any other files.
