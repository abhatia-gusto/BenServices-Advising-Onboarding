#!/usr/bin/env python3
"""Full re-pull of the v11 core metric data from Snowflake (as of today).

Outputs `v11_core_data.json` with:
  - advisors: list of {name, pe, erConfirm, rfd, tixSla, tixRate, quality} per advisor × month
  - availByMo: {name: {YYYY-MM: {eligible, met}}}
  - abandonByMo: {name: {YYYY-MM: {inbound, abandonedMod}}}
  - oppsByStatus: {name: {status: {YYYY-MM: count}}}
  - bosByMo: {name: {YYYY-MM: {fulfilled, cancelled}}}
  - ticketsByMo: {name: {YYYY-MM: {total, inSla}}}

Run order: roster → 7 metrics. Reuses existing source SQL files where possible.
"""
import json
import os
import sys
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
SNOW = os.path.expanduser("~/.local/bin/snow")
WIN_START = "2026-01-01"
import datetime as _dt
WIN_END = os.environ.get("PERF_END") or _dt.date.today().isoformat()   # dynamic: through today (auto-advances)
QTAG = ('{"qtag":{"version":"1.1.0","source":{"claude_code":'
        '{"username":"serene-sleepy-ramanujan","hostname":"claude",'
        '"source":"query-snowflake-skill"}}}}')


def run_sql(sql):
    full = f"ALTER SESSION SET QUERY_TAG = '{QTAG}';\n{sql}"
    cmd = [SNOW, "sql", "-c", "default", "-q", full, "--format", "JSON",
           "--enable-templating", "NONE", "--warehouse", "GUSTIE_ADHOC_WH"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    if proc.returncode != 0:
        print("STDERR:", proc.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"snow failed ({proc.returncode})")
    parsed = json.loads(proc.stdout)
    return parsed[-1] if parsed and isinstance(parsed[0], list) else parsed


def pull_opp_sla():
    """Per-advisor × month: ER Confirm SLA, RFD+Alt SLA, opp status counts.
    Wraps advising_opp_sla_v6_0.sql — the source of truth, same query the live
    Advising SLA daily refresh uses — for the methodology, adds aggregation.
    v6.0 includes OPEN opps + a 'Closed Admin' status; the closed-only guard
    below (is_open = false) keeps this a close-month cohort exactly as v5_3 did,
    while adopting v6.0's fixes (Closed Admin included, RDP/ALT target=5,
    9999-12-31 sentinel end-date fix)."""
    src = (HERE / "queries" / "advising_opp_sla_v6_0.sql").read_text()
    src = src.replace("{{date_start}}", WIN_START)\
             .replace("{{date_end}}", WIN_END)\
             .rstrip().rstrip(";")
    sql = f"""
    with src as (
      {src}
    )
    select
      owner_name as advisor_name,
      substr(cast(close_date_computed_month as varchar), 1, 7) as month_key,
      current_status as status,
      count(*) as n,
      count_if(er_slo_met = TRUE) as er_met,
      count_if(total_days_in_er_confirm > 0) as er_touched,
      sum(case when total_days_in_er_confirm > 0 then total_days_in_er_confirm else 0 end) as er_days_sum,
      count_if(rdp_slo_met = TRUE) as rdp_met,
      count_if(total_days_in_rdp > 0) as rdp_touched,
      sum(case when total_days_in_rdp > 0 then total_days_in_rdp else 0 end) as rdp_days_sum,
      count_if(alt_slo_met = TRUE) as alt_met,
      count_if(total_days_in_alt_requested > 0) as alt_touched,
      sum(case when total_days_in_alt_requested > 0 then total_days_in_alt_requested else 0 end) as alt_days_sum
    from src
    where owner_name is not null
      and is_open = false
    group by 1, 2, 3
    order by advisor_name, month_key, status
    """
    print(f"  [opp_sla] running...", file=sys.stderr)
    rows = run_sql(sql)
    print(f"  [opp_sla] {len(rows)} rows", file=sys.stderr)
    return rows


def pull_ticket_sla():
    """Per-advisor × month: Ticket SLA (closed within 5 days)."""
    src = (HERE / "queries" / "ticket_sla_by_flow_v3.sql").read_text()
    src = src.replace("{{Date Range Start}}", WIN_START)\
             .replace("{{Date Range End}}", WIN_END)\
             .rstrip().rstrip(";")
    sql = f"""
    with src as (
      {src}
    )
    select
      ticket_owner_name as advisor_name,
      substr(cast(date_trunc('month', ticket_closed_ts_mt) as varchar), 1, 7) as month_key,
      count(*) as total,
      count_if(time_to_close_min / 1440.0 <= 5) as met
    from src
    where ticket_owner_name is not null
      and ticket_closed_ts_mt is not null
    group by 1, 2
    order by advisor_name, month_key
    """
    print(f"  [ticket_sla] running...", file=sys.stderr)
    rows = run_sql(sql)
    print(f"  [ticket_sla] {len(rows)} rows", file=sys.stderr)
    return rows


def pull_bo_grain():
    """Per-advisor × month: BO fulfilled/cancelled + Ticket Rate (BenAdv tickets per fulfilled BO)."""
    src = (HERE / "queries" / "bo_grain_sla_v11.sql").read_text()
    src = src.replace("{{Date Range Start}}", WIN_START)\
             .replace("{{Date Range End}}", WIN_END)\
             .rstrip().rstrip(";")
    # Methodology matches BO SLA/SLO Dashboard "OA → Advising" rate:
    # - Numerator = TICKETS_TBL_OA_TO_BENADV (OA → Advising flow tickets)
    # - Denominator = Renewal fulfilled BOs only (record_type_name = 'Renewal')
    # - Attribution = Renewal Opp Owner (renewal_adv_opp_owner_name, fallback sfdc_opp_owner_name)
    sql = f"""
    with src as (
      {src}
    )
    select
      coalesce(renewal_adv_opp_owner_name, sfdc_opp_owner_name) as advisor_name,
      substr(cast(date_trunc('month', first_fulfilled_ts_mt) as varchar), 1, 7) as month_key,
      count_if(first_fulfilled_ts_mt is not null
               and cancel_flag = FALSE
               and record_type_name = 'Renewal') as fulfilled,
      count_if(cancel_flag = TRUE and record_type_name = 'Renewal') as cancelled,
      sum(case when first_fulfilled_ts_mt is not null
                and cancel_flag = FALSE
                and record_type_name = 'Renewal'
               then coalesce(tickets_tbl_oa_to_benadv, 0) else 0 end) as benadv_tix_on_fulfilled
    from src
    where coalesce(renewal_adv_opp_owner_name, sfdc_opp_owner_name) is not null
    group by 1, 2
    order by advisor_name, month_key
    """
    print(f"  [bo_grain] running...", file=sys.stderr)
    rows = run_sql(sql)
    print(f"  [bo_grain] {len(rows)} rows", file=sys.stderr)
    return rows


def pull_availability():
    """Per-advisor × month: eligible days + SLA-met days.
    Source of truth = shared av_pit_icmonth.sql (Call Dashboard point-in-time logic).
    Benefits Advising uses the HYBRID-HOURS ('adv') method there (was 80-105 band).
    Point-in-time roster; the app's active-roster anchor filters to current advisors."""
    src = (HERE / "queries" / "av_pit_icmonth.sql").read_text()\
        .replace("{{start_date}}", WIN_START).replace("{{end_date}}", WIN_END)\
        .rstrip().rstrip(";")
    sql = f"""
    with src as (
      {src}
    )
    select name as advisor_name, month as month_key,
           elig_days as eligible, sla_met_days as met
    from src
    where team = 'Benefits Advising' and name is not null and elig_days > 0
    order by advisor_name, month_key
    """
    print(f"  [availability] running (shared av_pit_icmonth, hybrid-hours)...", file=sys.stderr)
    rows = run_sql(sql)
    print(f"  [availability] {len(rows)} rows", file=sys.stderr)
    return rows


def pull_abandon():
    """Per-advisor × month: inbound calls + modified abandoned count.
    Source of truth = shared calls_pit_icmonth.sql (Call Dashboard point-in-time logic:
    per-agent, modified abandon excludes 'remove from queue', denom = inbound calls)."""
    src = (HERE / "queries" / "calls_pit_icmonth.sql").read_text()\
        .replace("{{start_date}}", WIN_START).replace("{{end_date}}", WIN_END)\
        .rstrip().rstrip(";")
    sql = f"""
    with src as (
      {src}
    )
    select name as advisor_name, month as month_key,
           inbound_ct as inbound, abandoned_mod_ct as abandoned_mod
    from src
    where team = 'Benefits Advising' and name is not null
    order by advisor_name, month_key
    """
    print(f"  [abandon] running (shared calls_pit_icmonth)...", file=sys.stderr)
    rows = run_sql(sql)
    print(f"  [abandon] {len(rows)} rows", file=sys.stderr)
    return rows


def pull_level_ai():
    """Per-advisor × month: Level AI evaluation count + score sum (for avg %)."""
    src = (HERE / "queries" / "level_ai_qa.sql").read_text()
    src = src.replace("{{ start_date }}", WIN_START)\
             .replace("{{ end_date }}", WIN_END)\
             .rstrip().rstrip(";")
    sql = f"""
    with src as (
      {src}
    )
    select
      full_name as advisor_name,
      to_char(convo_month, 'YYYY-MM') as month_key,
      count(*) as evals,
      sum(evaluation_score * 100) as score_sum_pct
    from src
    where full_name is not null
    group by 1, 2
    order by advisor_name, month_key
    """
    print(f"  [level_ai] running...", file=sys.stderr)
    rows = run_sql(sql)
    print(f"  [level_ai] {len(rows)} rows", file=sys.stderr)
    return rows


def pull_pe_map():
    """Per-advisor CURRENT PE (opportunity_owner_pe_name, fallback at-close) —
    same source the Advising SLA ticket-rate PE uses. Keeps Advising Perf PE
    auto-current instead of relying on the hand-maintained peMap."""
    src = (HERE / "queries" / "advising_opp_sla_v6_0.sql").read_text()
    src = src.replace("{{date_start}}", WIN_START)\
             .replace("{{date_end}}", WIN_END)\
             .rstrip().rstrip(";")
    sql = f"""
    with src as (
      {src}
    )
    select owner_name as advisor,
           max_by(coalesce(pe_name, pe_name_at_close), close_date_computed) as pe
    from src
    where owner_name is not null
    group by 1
    """
    print("  [pe_map] running...", file=sys.stderr)
    rows = run_sql(sql)
    return {r["ADVISOR"]: r["PE"] for r in rows if r.get("ADVISOR") and r.get("PE")}


def pull_adv_roster():
    """Widened Advising roster (Benefits/Customer Advising, is_pe=false, ALL statuses) with
    last-known PE. Drives union-from-data scope + active-vs-former in inject_v11_core_data."""
    sql = """
    select e.name as NAME, e.status as STATUS, coalesce(pe.name, e.mu_name) as MANAGER
    from bi.gusto_employees e
    left join bi.gusto_employees pe on e.pe_sfdc_ee_id=pe.sfdc_ee_id and pe.current_flag=true
    where e.current_flag=true and e.is_pe=false
      and e.sub_team in ('Benefits Advising','Customer Advising')
    """
    return run_sql(sql)


def main():
    print("=== Pulling v11 core data from Snowflake ===", file=sys.stderr)
    opp_rows = pull_opp_sla()
    tix_rows = pull_ticket_sla()
    bo_rows = pull_bo_grain()
    avail_rows = pull_availability()
    abandon_rows = pull_abandon()
    lai_rows = pull_level_ai()
    pe_map = pull_pe_map()
    adv_roster = pull_adv_roster()

    out = {
        "pe_map": pe_map,
        "adv_roster": adv_roster,
        "opp": opp_rows,
        "ticket_sla": tix_rows,
        "bo_grain": bo_rows,
        "availability": avail_rows,
        "abandon": abandon_rows,
        "level_ai": lai_rows,
    }
    out_path = HERE / "v11_core_data.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"\n[done] Wrote {out_path}", file=sys.stderr)
    print(f"  opp_sla: {len(opp_rows)} rows", file=sys.stderr)
    print(f"  ticket_sla: {len(tix_rows)} rows", file=sys.stderr)
    print(f"  bo_grain: {len(bo_rows)} rows", file=sys.stderr)
    print(f"  availability: {len(avail_rows)} rows", file=sys.stderr)
    print(f"  abandon: {len(abandon_rows)} rows", file=sys.stderr)
    print(f"  level_ai: {len(lai_rows)} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
