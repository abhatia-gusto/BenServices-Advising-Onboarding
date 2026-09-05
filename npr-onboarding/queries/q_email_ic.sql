SELECT IC,
  TO_CHAR(DATE_TRUNC('month',TPC),'YYYY-MM') AS MONTH,
  SUM(IFF(ST IN ('Responded (Within SLA)','Responded (Past SLA)'),1,0)) AS TOTAL,
  SUM(IFF(ST='Responded (Within SLA)',1,0)) AS MET
FROM (
  SELECT
    CASE
      WHEN COALESCE(bo_record_type,'')='' THEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name)
      WHEN benefit_order_status_at_tp_start_ts IN ('With Sales','With Advising') AND COALESCE(bo_record_type,'') NOT IN ('Benefits BYB','Benefits BoR')
           THEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name, bo_owner_name_at_tp, current_benefit_order_owner_name)
      WHEN bo_owner_name_at_tp IS NULL AND COALESCE(benefit_order_status_at_tp_start_ts,'')='' AND COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name) IS NOT NULL
           THEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name)
      ELSE COALESCE(bo_owner_name_at_tp, current_benefit_order_owner_name, opp_owner_name_at_tp, current_opportunity_owner_name)
    END AS IC,
    CASE
      WHEN COALESCE(bo_record_type,'')='' THEN COALESCE(opp_owner_subteam_at_tp, opp_owner_subteam)
      WHEN benefit_order_status_at_tp_start_ts IN ('With Sales','With Advising') AND COALESCE(bo_record_type,'') NOT IN ('Benefits BYB','Benefits BoR')
           THEN CASE WHEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name) IS NOT NULL THEN COALESCE(opp_owner_subteam_at_tp, opp_owner_subteam) ELSE COALESCE(bo_owner_subteam_at_tp, bo_owner_subteam) END
      WHEN bo_owner_name_at_tp IS NULL AND COALESCE(benefit_order_status_at_tp_start_ts,'')='' AND COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name) IS NOT NULL
           THEN COALESCE(opp_owner_subteam_at_tp, opp_owner_subteam)
      ELSE COALESCE(bo_owner_subteam_at_tp, bo_owner_subteam)
    END AS RSUB,
    tp_created_ts AS TPC,
    inbound_email_response_status AS ST
  FROM (
-- ============================================================
-- AB Email SLA — Advising, OA, BYB & BT
-- Version: v8
-- Redash: https://redash.zp-int.com/queries/179297
-- ============================================================
--
-- QUERY PURPOSE
-- ─────────────
--   One row per inbound email touchpoint on Benefits cases.
--   Computes SLA status (Met/Missed/Cleared/Pending) using HOOP
--   business-hours timing, with automated-reply filtering,
--   gap-based clearing logic, and point-in-time case owner
--   attribution via the native touchpoint field.
--
-- PARAMETERS
-- ──────────
--   2026-01-01     Date   Start of reporting window (MT)  [change this literal to move the window; appears at 3 anchors below]
--   CURRENT_DATE() Date   End of reporting window (MT)  [auto-advances each run; NOT capped at a fixed date]
--   (SLA threshold hardcoded to 240 HOOP minutes = 4 hours)
--
-- DATA SOURCES
-- ────────────
--   bi.benefit_order_touchpoints           Inbound + outbound email touchpoints
--   bi.cases                               Case metadata, filtering, IDs
--   bi.gusto_employees                     Employee info (current + historical)
--   bi.sfdc_users_gusto_employees_view     Current employee lookup (PE chain)
--   bi.benefit_orders                      BO metadata (record type)
--   bi.benefit_order_status_change_history BO owner at TP (stage history)
--   bi_reporting.advising_opportunities    Opp owner name
--   bi.sfdc_opportunity_history            Opp owner at TP (owner history)
--   bi.static_calendar                     Business day flag (HOOP calculations)
--
-- CTE SUMMARY
-- ───────────
--   ee_info           Current employee lookup (current_flag=true).
--                     Used for: advocate, BO owner, case owner current
--                     team, fallback reply owner, opp owner.
--
--   ee_hist           Historical employee lookup (ALL rows, no
--                     current_flag). Joined on sfdc_user_id +
--                     effect_start_dt/effect_end_dt date range.
--                     Used for: case owner team AT TIME of touchpoint.
--
--   inbound           All inbound email touchpoints in date window.
--                     Date params converted to UTC via Mountain Time
--                     interpretation.
--
--   outbound          All NON-AUTOMATED outbound email touchpoints
--                     (date window +8d for fallback matching).
--                     v8: allowlist filter — sender must exist in
--                     ee_info (current employees only).
--
--   fallback_reply    First non-automated outbound reply on the same
--   / fr              case within 7 days of each inbound.
--
--   pending_hoop      Precise elapsed HOOP minutes for pending items.
--                     Only computed for items with no non-automated
--                     response and no clearing.
--
--   fallback_hoop     Precise HOOP minutes for fallback-reply responses.
--                     v8: also fires when primary reply is automated
--                     (owner_name is NULL) but fallback found a
--                     non-automated reply.
--
-- AUTOMATED REPLY FILTERING (v8)
-- ───────────────────────────────
--   Automated outbound emails (ZenPayroll/exec ~6,655/mo, BizTech/
--   Integration Users ~400/mo) are excluded from response matching
--   via two layers:
--
--   Layer A (allowlist): The outbound CTE requires the sender to
--   exist in ee_info (current employees). Any non-employee sender
--   is excluded — catches exec, Integration Users, and any future
--   automated account without maintaining a blocklist.
--
--   Layer B (primary override): The upstream pipeline may have
--   already linked an automated outbound as first_outbound_reply_*.
--   These are detected by first_outbound_reply_owner_name IS NULL
--   (automated users don't resolve in ee_info). When detected, the
--   primary reply is ignored and the clean fallback reply is used.
--
--   "Non-automated response" = primary reply with owner_name populated,
--   OR fallback reply (which excludes Integration Users by construction).
--
-- GAP-BASED CLEARING LOGIC (v8)
-- ──────────────────────────────
--   Diagnostic finding: 70% of "cleared then responded" emails have a
--   clearing-to-response gap of < 1 minute. Agents clear the
--   requires-action flag as a workflow step immediately before or
--   simultaneously with sending the reply. Only ~10% have a gap > 4
--   hours, indicating the clearing was a genuine "no response needed"
--   decision and the later outbound is unrelated (scenario 4).
--
--   Algorithm:
--     1. Not response required → skip
--     2. Has non-automated response:
--        a. No clearing → classify by response HOOP (Met/Missed)
--        b. Clearing exists, gap ≤ 240 wall-clock min →
--           workflow clearing, classify by response HOOP
--        c. Clearing exists, gap > 240 wall-clock min →
--           scenario 4 → "Cleared" (excluded from SLA)
--     3. No non-automated response:
--        a. Clearing exists → "Cleared" (excluded from SLA)
--        b. No clearing, HOOP > 240 → "Pending (Missed SLA - aging)"
--        c. No clearing → "Pending response"
--
--   Gap = datediff(minute, clearing_ts, clean_response_ts).
--   Uses wall-clock minutes (not HOOP) — this is a classification
--   threshold for intent, not a performance metric.
--
-- NATIVE CASE OWNER FIELD (v8)
-- ─────────────────────────────
--   v8 uses tp.case_owner_at_tp_start_ts (native touchpoint field)
--   instead of the case_owner_asof CTE that walked
--   bi.cases_field_history. Diagnostic confirmed 96% resolve rate.
--   Drops one CTE and one join. Fallback to BO owner at dashboard
--   level for NULLs.
--
-- SLA METHODOLOGY
-- ───────────────
--   • SLA target: 240 HOOP minutes (4 hours), hardcoded.
--   • SLA Rate = Met ÷ (Met + Missed).
--     Cleared and Pending are excluded from the denominator.
--   • HOOP window: 8:00 AM – 5:00 PM Mountain Time (540 mins/day).
--
-- CLOSED CASE FILTER
-- ──────────────────
--   Inbound emails on cases where case_status_at_tp_start_ts = 'Closed'
--   are excluded. Response tracking is unreliable on closed cases.
--
-- TIMEZONE HANDLING
-- ─────────────────
--   • touchpoint_start_ts is stored in UTC.
--   • Date parameters interpreted as Mountain Time via:
--       convert_timezone('America/Denver','UTC', param::timestamp_ntz)
--   • All _mt output columns use convert_timezone('UTC','America/Denver').
--
-- KNOWN LIMITATIONS
-- ─────────────────
--   1. Historical team lookup (ee_hist) may produce duplicates if
--      overlapping date ranges are introduced upstream. Monitor row
--      counts on version change.
--
--   2. case_owner_at_tp_start_ts is NULL for ~4% of touchpoints.
--      Dashboard falls back to BO owner for attribution.
--
--   3. Automated reply detection relies on first_outbound_reply_owner_name
--      being NULL. If a non-automated reply has a NULL owner due to an
--      upstream join failure, it would incorrectly fall to the fallback.
--      This is rare and conservative (fallback finds the next real reply).
--
--   4. The 240 wall-clock minute gap threshold is a heuristic. Edge
--      cases exist where an agent legitimately cleared and responded
--      5+ hours later (would be classified as Cleared), or where an
--      unrelated outbound fires within 4 hours of clearing (would be
--      classified as a response).
--
--   5. opp_owner_ee join is on ee_name (string match), not user_id.
--
--   6. OWNER-AT-TP TEAM RESOLUTION: All three owner-at-TP lookups
--      resolve the correct PERSON at the time of the touchpoint.
--      However, their team/subteam resolution differs:
--        • Case owner: HISTORICAL team via ee_hist (point-in-time).
--        • BO owner:   CURRENT team via ee_info. If the person
--          changed teams since the TP, subteam reflects today.
--        • Opp owner:  CURRENT team via ee_info. Same caveat.
--      To upgrade BO/opp to historical, add ee_hist joins (same
--      pattern as case_owner_hist). Deferred — current team is
--      accurate for ~98% of rows given low team-mobility rates.
--
-- CHANGES FROM v7
-- ───────────────
--  13. AUTOMATED OUTBOUND ALLOWLIST: outbound CTE requires sender to
--      exist in ee_info (current employees). Catches ZenPayroll/exec
--      (~6,655/mo), Integration Users (~400/mo), and any future
--      automated sender. Replaces the original Integration Users
--      blocklist which missed the exec account.
--
--  14. AUTOMATED PRIMARY REPLY OVERRIDE: When upstream-linked
--      first_outbound_reply has a NULL owner_name (automated sender),
--      the primary reply is ignored. SLA classification falls through
--      to the fallback reply if one exists.
--
--  15. GAP-BASED CLEARING: Replaces clearing-first logic. If both
--      clearing and a non-automated response exist, the wall-clock
--      gap between them determines classification:
--        ≤ 240 min → workflow clearing → classify by HOOP
--        > 240 min → scenario 4 → "Cleared"
--      Fixes v7's over-classification where 77% of responded emails
--      were incorrectly bucketed as "Cleared".
--
--  16. NATIVE CASE OWNER: Replaced case_owner_asof CTE (which walked
--      bi.cases_field_history) with tp.case_owner_at_tp_start_ts.
--      Drops one CTE and simplifies joins. 96% resolve rate confirmed
--      by diagnostic.
--
--  17. FALLBACK_HOOP BROADENED: Now also fires when primary reply
--      exists but is automated (owner_name IS NULL), not just when
--      primary reply is completely absent.
--
--  18. PENDING_HOOP FILTER UPDATED: Uses owner_name IS NULL check
--      instead of has_future_outbound_reply_flag for consistency
--      with the automated-reply override logic.
--
--  19. BO OWNER AT TP: New join to benefit_order_status_change_history
--      (sfdc_stage_owner_derive_method = 'order_owner') gives
--      point-in-time BO owner. Diagnostic confirmed 22.7% of BOs
--      change ownership during their lifecycle. New columns:
--      bo_owner_name_at_tp, bo_owner_subteam_at_tp.
--
--  20. OPP OWNER AT TP: New join to sfdc_opportunity_history gives
--      point-in-time opp owner via OWNER (user ID) + date range.
--      New columns: opp_owner_name_at_tp, opp_owner_subteam_at_tp.
-- ============================================================
with ee_info as (
    select
        ee.name as ee_name
        , ee.sfdc_user_id
        , ee.sfdc_ee_id
        , ee.sfdc_userrole_name
        , ee.sub_team
        , ee.team
        , ee2.pe
        , ee2.pe_sfdc_ee_id
        , ee3.pe as pepe
        , ee3.pe_sfdc_ee_id as pepe_sfdc_ee_id
        , ee2.sub_team as current_sub_team
        , ee2.team as current_team
    from bi.sfdc_users_gusto_employees_view as ee
    left join bi.gusto_employees as ee2
        on ee2.sfdc_ee_id = ee.sfdc_ee_id
        and ee2.current_flag
    left join bi.gusto_employees as ee3
        on ee3.sfdc_ee_id = ee2.pe_sfdc_ee_id
        and ee3.current_flag
    where ee.current_flag
),
ee_hist as (
    select
        sfdc_ee_id
        , sfdc_user_id
        , name as ee_name
        , team
        , sub_team
        , effect_start_dt
        , coalesce(effect_end_dt, '9999-12-31'::date) as effect_end_dt
    from bi.gusto_employees
),
inbound as (
    select
        c.id as sfdc_case_id
        , c.trimmed_case_id
        , c.casenumber
        , tp.touchpoint_object_id
        , tp.created_ts as tp_created_ts
        , tp.touchpoint_start_ts
        , tp.channel
        , tp.direction
        , tp.touchpoint_system_object_source
        , tp.carrier_case_flag
        , coalesce(tp.sfdc_opportunity_id, c.sfdc_opportunity_id) as sfdc_opportunity_id
        , coalesce(tp.sfdc_benefit_order_id, c.sfdc_benefit_order_id) as sfdc_benefit_order_id
        , tp.sfdc_advocate_user_id
        , tp.advocate_role_name
        , tp.case_status_at_tp_start_ts
        , tp.benefit_order_status_at_tp_start_ts
        , tp.opportunity_status_at_tp_start_ts
        , tp.connect_with_customer_flag as response_required_flag
        , tp.has_future_outbound_reply_flag
        , tp.first_outbound_reply_ts
        , tp.first_outbound_reply_owner_id
        , tp.first_outbound_reply_owner_name
        , tp.next_requires_action_case_flag_set_to_false_ts
        , tp.time_to_email_response_mins
        , tp.total_time_to_email_response_hoop_mins
        , tp.back_to_back_inbound_email_flag
        , tp.case_owner_at_tp_start_ts
    from bi.cases c
    join bi.benefit_order_touchpoints tp
        on tp.sfdc_case_id = c.id
    where
        c.type <> 'Carrier Submission'
        and tp.carrier_case_flag = false
        and tp.channel = 'Email'
        and tp.direction = 'Inbound'
        and coalesce(tp.case_status_at_tp_start_ts, '') <> 'Closed'
        and tp.touchpoint_start_ts >=
            convert_timezone('America/Denver', 'UTC', '2026-01-01'::timestamp_ntz)
        and tp.touchpoint_start_ts <
            convert_timezone('America/Denver', 'UTC', (CURRENT_DATE() + 1)::timestamp_ntz)
),
outbound as (
    select
        tp.sfdc_case_id
        , tp.touchpoint_start_ts as outbound_ts
        , tp.sfdc_advocate_user_id as outbound_actor_user_id
        , tp.advocate_role_name as outbound_actor_role_name
        , tp.touchpoint_system_object_source as outbound_source
        , tp.touchpoint_object_id as outbound_touchpoint_object_id
    from bi.benefit_order_touchpoints tp
    where
        tp.channel = 'Email'
        and tp.direction = 'Outbound'
        and tp.carrier_case_flag = false
        and exists (
            select 1 from ee_info ei
            where ei.sfdc_user_id = tp.sfdc_advocate_user_id
        )
        and tp.touchpoint_start_ts >=
            convert_timezone('America/Denver', 'UTC', '2026-01-01'::timestamp_ntz)
        and tp.touchpoint_start_ts <
            convert_timezone('America/Denver', 'UTC', (CURRENT_DATE() + 8)::timestamp_ntz)
),
fallback_reply as (
    select
        i.touchpoint_object_id as inbound_touchpoint_object_id
        , o.outbound_ts
        , o.outbound_actor_user_id
        , o.outbound_actor_role_name
        , o.outbound_source
        , o.outbound_touchpoint_object_id
        , row_number() over (
            partition by i.touchpoint_object_id
            order by o.outbound_ts asc
          ) as rn
    from inbound i
    join outbound o
      on o.sfdc_case_id = i.sfdc_case_id
     and o.outbound_ts > i.touchpoint_start_ts
     and o.outbound_ts <= dateadd('day', 7, i.touchpoint_start_ts)
),
fr as (
    select *
    from fallback_reply
    where rn = 1
),
pending_hoop as (
    select
        sub.touchpoint_object_id
        , sum(sub.elapsed_business_minutes) as elapsed_hoop_mins
    from (
        select
            p.touchpoint_object_id
            , bd.date
            , case
                when bd.date = p.tp_mt::date and bd.date = p.now_mt::date
                 and p.tp_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.tp_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                 and p.now_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.now_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', p.tp_mt, p.now_mt)
                when bd.date = p.tp_mt::date and bd.date = p.now_mt::date
                 and p.tp_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.now_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.now_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', dateadd('hour', 8, bd.date::timestamp_ntz), p.now_mt)
                when bd.date = p.tp_mt::date and bd.date = p.now_mt::date
                 and p.tp_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.tp_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                 and p.now_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', p.tp_mt, dateadd('hour', 17, bd.date::timestamp_ntz))
                when bd.date = p.tp_mt::date and bd.date = p.now_mt::date
                 and p.tp_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.now_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then 540
                when bd.date = p.tp_mt::date and bd.date <> p.now_mt::date
                 and p.tp_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.tp_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', p.tp_mt, dateadd('hour', 17, bd.date::timestamp_ntz))
                when bd.date = p.tp_mt::date and bd.date <> p.now_mt::date
                 and p.tp_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                then 540
                when bd.date = p.tp_mt::date and bd.date <> p.now_mt::date
                 and p.tp_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then 0
                when bd.date > p.tp_mt::date and bd.date < p.now_mt::date
                then 540
                when bd.date <> p.tp_mt::date and bd.date = p.now_mt::date
                 and p.now_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and p.now_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', dateadd('hour', 8, bd.date::timestamp_ntz), p.now_mt)
                when bd.date <> p.tp_mt::date and bd.date = p.now_mt::date
                 and p.now_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then 540
                when bd.date <> p.tp_mt::date and bd.date = p.now_mt::date
                 and p.now_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                then 0
                else 0
              end as elapsed_business_minutes
        from (
            select
                i.touchpoint_object_id
                , convert_timezone('UTC', 'America/Denver', i.touchpoint_start_ts) as tp_mt
                , convert_timezone('UTC', 'America/Denver', current_timestamp()) as now_mt
            from inbound i
            left join fr
                on fr.inbound_touchpoint_object_id = i.touchpoint_object_id
            where i.response_required_flag = true
              and i.first_outbound_reply_owner_name is null
              and fr.outbound_ts is null
              and i.next_requires_action_case_flag_set_to_false_ts is null
        ) p
        join bi.static_calendar bd
            on bd.business_day = true
           and bd.date >= p.tp_mt::date
           and bd.date <= p.now_mt::date
    ) sub
    group by sub.touchpoint_object_id
),
fallback_hoop as (
    select
        sub.touchpoint_object_id
        , sum(sub.elapsed_business_minutes) as elapsed_hoop_mins
    from (
        select
            f.touchpoint_object_id
            , bd.date
            , case
                when bd.date = f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.tp_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.tp_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                 and f.reply_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.reply_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', f.tp_mt, f.reply_mt)
                when bd.date = f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.tp_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.reply_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.reply_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', dateadd('hour', 8, bd.date::timestamp_ntz), f.reply_mt)
                when bd.date = f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.tp_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.tp_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                 and f.reply_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', f.tp_mt, dateadd('hour', 17, bd.date::timestamp_ntz))
                when bd.date = f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.tp_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.reply_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then 540
                when bd.date = f.tp_mt::date and bd.date <> f.reply_mt::date
                 and f.tp_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.tp_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', f.tp_mt, dateadd('hour', 17, bd.date::timestamp_ntz))
                when bd.date = f.tp_mt::date and bd.date <> f.reply_mt::date
                 and f.tp_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                then 540
                when bd.date = f.tp_mt::date and bd.date <> f.reply_mt::date
                 and f.tp_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then 0
                when bd.date > f.tp_mt::date and bd.date < f.reply_mt::date
                then 540
                when bd.date <> f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.reply_mt >= dateadd('hour', 8, bd.date::timestamp_ntz)
                 and f.reply_mt <= dateadd('hour', 17, bd.date::timestamp_ntz)
                then datediff('minute', dateadd('hour', 8, bd.date::timestamp_ntz), f.reply_mt)
                when bd.date <> f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.reply_mt > dateadd('hour', 17, bd.date::timestamp_ntz)
                then 540
                when bd.date <> f.tp_mt::date and bd.date = f.reply_mt::date
                 and f.reply_mt < dateadd('hour', 8, bd.date::timestamp_ntz)
                then 0
                else 0
              end as elapsed_business_minutes
        from (
            select
                i.touchpoint_object_id
                , convert_timezone('UTC', 'America/Denver', i.touchpoint_start_ts) as tp_mt
                , convert_timezone('UTC', 'America/Denver', fr.outbound_ts) as reply_mt
            from inbound i
            join fr
                on fr.inbound_touchpoint_object_id = i.touchpoint_object_id
            where i.first_outbound_reply_owner_name is null
              and fr.outbound_ts is not null
        ) f
        join bi.static_calendar bd
            on bd.business_day = true
           and bd.date >= f.tp_mt::date
           and bd.date <= f.reply_mt::date
    ) sub
    group by sub.touchpoint_object_id
)
select
    i.touchpoint_object_id
    , i.sfdc_case_id
    , i.casenumber
    , 'https://gusto.my.salesforce.com/' || i.trimmed_case_id || '?srPos=0&srKp=500' as case_link
    , i.sfdc_opportunity_id
    , i.sfdc_benefit_order_id
    , bo.record_type_name as bo_record_type
    , op.owner_name     as current_opportunity_owner_name
    , opp_owner_ee.team     as opp_owner_team
    , opp_owner_ee.sub_team as opp_owner_subteam
    , opp_owner_at_tp_ee.ee_name  as opp_owner_name_at_tp
    , opp_owner_at_tp_ee.sub_team as opp_owner_subteam_at_tp
    , bo_owner.ee_name  as current_benefit_order_owner_name
    , bo_owner.sub_team as bo_owner_subteam
    , bo_owner_at_tp_ee.ee_name  as bo_owner_name_at_tp
    , bo_owner_at_tp_ee.sub_team as bo_owner_subteam_at_tp
    , case_owner_tp.ee_name  as case_owner_name_at_tp
    , case_owner_tp.sub_team as case_owner_current_subteam
    , case_owner_hist.team     as case_owner_team_at_tp
    , case_owner_hist.sub_team as case_owner_subteam_at_tp
    , i.tp_created_ts
    , i.touchpoint_start_ts
    , convert_timezone('UTC', 'America/Denver', i.touchpoint_start_ts) as touchpoint_start_ts_mt
    , i.channel
    , i.direction
    , i.touchpoint_system_object_source
    , i.carrier_case_flag
    , i.sfdc_advocate_user_id
    , i.advocate_role_name
    , ee.ee_name
    , ee.team     as advocate_team
    , ee.sub_team as advocate_sub_team
    , ee.pe
    , ee.pe_sfdc_ee_id
    , ee.pepe
    , ee.pepe_sfdc_ee_id
    , i.case_status_at_tp_start_ts
    , i.benefit_order_status_at_tp_start_ts
    , i.opportunity_status_at_tp_start_ts
    , i.response_required_flag
    , i.has_future_outbound_reply_flag
    , i.first_outbound_reply_ts
    , convert_timezone('UTC', 'America/Denver', i.first_outbound_reply_ts) as first_outbound_reply_ts_mt
    , i.first_outbound_reply_owner_id
    , i.first_outbound_reply_owner_name
    , i.next_requires_action_case_flag_set_to_false_ts
    , convert_timezone('UTC', 'America/Denver', i.next_requires_action_case_flag_set_to_false_ts) as requires_action_cleared_ts_mt
    , fr.outbound_ts as fallback_first_outbound_reply_ts
    , convert_timezone('UTC', 'America/Denver', fr.outbound_ts) as fallback_first_outbound_reply_ts_mt
    , fr.outbound_actor_user_id as fallback_first_outbound_reply_owner_id
    , fallback_owner.ee_name as fallback_first_outbound_reply_owner_name
    , fr.outbound_touchpoint_object_id as fallback_outbound_touchpoint_object_id
    , fr.outbound_source as fallback_outbound_source
    , i.time_to_email_response_mins
    , (i.time_to_email_response_mins::float / 60) as time_to_email_response_hrs
    , i.total_time_to_email_response_hoop_mins
    , (i.total_time_to_email_response_hoop_mins::float / 60) as hoop_time_to_email_response_hrs
    , case
        when i.first_outbound_reply_ts is not null and i.first_outbound_reply_owner_name is null
        then true else false
      end as automated_primary_reply_flag
    , coalesce(
        case when i.first_outbound_reply_owner_name is not null
             then i.first_outbound_reply_ts end,
        fr.outbound_ts
      ) as response_ts_used
    , convert_timezone('UTC', 'America/Denver',
        coalesce(
            case when i.first_outbound_reply_owner_name is not null
                 then i.first_outbound_reply_ts end,
            fr.outbound_ts
        )) as response_ts_used_mt
    , coalesce(
        case when i.first_outbound_reply_owner_name is not null
             then i.total_time_to_email_response_hoop_mins end,
        fh.elapsed_hoop_mins
      ) as response_time_mins_used
    , case
        when i.first_outbound_reply_owner_name is not null then true
        when fr.outbound_ts is not null then true
        else false
      end as responded_flag_including_fallback
    , case
        when i.next_requires_action_case_flag_set_to_false_ts is not null
         and coalesce(
               case when i.first_outbound_reply_owner_name is not null
                    then i.first_outbound_reply_ts end,
               fr.outbound_ts
             ) is not null
        then datediff('minute',
               i.next_requires_action_case_flag_set_to_false_ts,
               coalesce(
                   case when i.first_outbound_reply_owner_name is not null
                        then i.first_outbound_reply_ts end,
                   fr.outbound_ts
               ))
        else null
      end as clearing_to_response_gap_mins
    , case
        when ph.elapsed_hoop_mins is not null and ph.elapsed_hoop_mins > 240
        then 'X' else null
      end as pending_past_sla_flag
    , round(ph.elapsed_hoop_mins / 60.0, 1) as elapsed_hoop_hrs_since_pending
    , case
        when i.response_required_flag is null or i.response_required_flag = false
        then 'Not response required'
        when i.response_required_flag = true
         and (i.first_outbound_reply_owner_name is not null or fr.outbound_ts is not null)
         and i.next_requires_action_case_flag_set_to_false_ts is not null
         and datediff('minute',
               i.next_requires_action_case_flag_set_to_false_ts,
               coalesce(
                   case when i.first_outbound_reply_owner_name is not null
                        then i.first_outbound_reply_ts end,
                   fr.outbound_ts
               )) > 240
        then 'Cleared (Requires Action false)'
        when i.response_required_flag = true
         and (i.first_outbound_reply_owner_name is not null or fr.outbound_ts is not null)
         and coalesce(
               case when i.first_outbound_reply_owner_name is not null
                    then i.total_time_to_email_response_hoop_mins end,
               fh.elapsed_hoop_mins
             ) is not null
         and coalesce(
               case when i.first_outbound_reply_owner_name is not null
                    then i.total_time_to_email_response_hoop_mins end,
               fh.elapsed_hoop_mins
             ) <= 240
        then 'Responded (Within SLA)'
        when i.response_required_flag = true
         and (i.first_outbound_reply_owner_name is not null or fr.outbound_ts is not null)
         and coalesce(
               case when i.first_outbound_reply_owner_name is not null
                    then i.total_time_to_email_response_hoop_mins end,
               fh.elapsed_hoop_mins
             ) is not null
         and coalesce(
               case when i.first_outbound_reply_owner_name is not null
                    then i.total_time_to_email_response_hoop_mins end,
               fh.elapsed_hoop_mins
             ) > 240
        then 'Responded (Past SLA)'
        when i.response_required_flag = true
         and (i.first_outbound_reply_owner_name is not null or fr.outbound_ts is not null)
        then 'Responded (Response time unknown)'
        when i.response_required_flag = true
         and i.next_requires_action_case_flag_set_to_false_ts is not null
        then 'Cleared (Requires Action false)'
        when i.response_required_flag = true
         and ph.elapsed_hoop_mins is not null
         and ph.elapsed_hoop_mins > 240
        then 'Pending (Missed SLA - aging)'
        when i.response_required_flag = true
        then 'Pending response'
        else null
      end as inbound_email_response_status
    , i.back_to_back_inbound_email_flag
from inbound i
left join bi_reporting.advising_opportunities op
    on op.sfdc_object_id = i.sfdc_opportunity_id
left join bi.benefit_orders bo
    on bo.sfdc_benefit_order_id = i.sfdc_benefit_order_id
left join ee_info ee
    on ee.sfdc_user_id = i.sfdc_advocate_user_id
left join ee_info bo_owner
    on bo_owner.sfdc_user_id = bo.sfdc_benefit_order_owner_id
left join bi.benefit_order_status_change_history boh
    on boh.sfdc_object_id = i.sfdc_benefit_order_id
   and boh.sfdc_stage_owner_derive_method = 'order_owner'
   and i.touchpoint_start_ts >= boh.start_time
   and i.touchpoint_start_ts < boh.end_time
left join ee_info bo_owner_at_tp_ee
    on bo_owner_at_tp_ee.sfdc_user_id = boh.sfdc_stage_owner_id
left join ee_info case_owner_tp
    on case_owner_tp.sfdc_user_id = i.case_owner_at_tp_start_ts
left join ee_hist case_owner_hist
    on case_owner_hist.sfdc_user_id = i.case_owner_at_tp_start_ts
   and convert_timezone('UTC', 'America/Denver', i.touchpoint_start_ts)::date
       >= case_owner_hist.effect_start_dt
   and convert_timezone('UTC', 'America/Denver', i.touchpoint_start_ts)::date
       < case_owner_hist.effect_end_dt
left join fr
    on fr.inbound_touchpoint_object_id = i.touchpoint_object_id
left join ee_info fallback_owner
    on fallback_owner.sfdc_user_id = fr.outbound_actor_user_id
left join pending_hoop ph
    on ph.touchpoint_object_id = i.touchpoint_object_id
left join fallback_hoop fh
    on fh.touchpoint_object_id = i.touchpoint_object_id
left join ee_info opp_owner_ee
    on opp_owner_ee.ee_name = op.owner_name
left join bi.sfdc_opportunity_history oh
    on oh.opportunity_id = i.sfdc_opportunity_id
   and i.touchpoint_start_ts >= oh.effect_start_dt
   and i.touchpoint_start_ts < coalesce(oh.effect_end_dt, '9999-12-31'::timestamp_ntz)
left join ee_info opp_owner_at_tp_ee
    on opp_owner_at_tp_ee.sfdc_user_id = oh.owner
where
    (
        op.sfdc_object_id is not null
        or (
            i.sfdc_opportunity_id is not null
            and i.sfdc_benefit_order_id is not null
        )
    )

) q
  WHERE response_required_flag = TRUE
    AND inbound_email_response_status IS NOT NULL
    AND inbound_email_response_status <> 'Pending response'
    AND tp_created_ts BETWEEN '2026-01-01' AND CURRENT_TIMESTAMP()
) r
WHERE RSUB IN ('New Plan & Renewal Onboarding','Onboarding Advocacy') AND IC IS NOT NULL
GROUP BY 1,2 ORDER BY 1,2