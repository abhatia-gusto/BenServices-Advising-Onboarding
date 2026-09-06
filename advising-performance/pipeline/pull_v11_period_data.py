#!/usr/bin/env python3
"""Pull per-month per-channel data from Snowflake for v11.

Two outputs:
  - Calls per advisor × month: total/inbound/outbound counts + avg/median durations
  - Level AI per advisor × month × channel: count of evals per channel

Both are saved to JSON and ready for the injector.
"""
import json
import os
import sys
import subprocess
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SNOW = os.path.expanduser("~/.local/bin/snow")
WIN_START = "2026-01-01"
import datetime as _dt
WIN_END = os.environ.get("PERF_END") or _dt.date.today().isoformat()  # dynamic: through today (auto-advances)
QTAG = ('{"qtag":{"version":"1.1.0","source":{"claude_code":'
        '{"username":"serene-sleepy-ramanujan","hostname":"claude",'
        '"source":"query-snowflake-skill"}}}}')


def run_sql(sql, fmt="JSON"):
    full = f"ALTER SESSION SET QUERY_TAG = '{QTAG}';\n{sql}"
    cmd = [SNOW, "sql", "-c", "default", "-q", full, "--format", fmt,
           "--enable-templating", "NONE", "--warehouse", "GUSTIE_ADHOC_WH"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print("SQL STDERR:", proc.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"snow failed ({proc.returncode})")
    # snow JSON with multiple statements returns a list of result sets.
    # Grab the LAST one (our actual query — first is the ALTER SESSION).
    parsed = json.loads(proc.stdout)
    if parsed and isinstance(parsed[0], list):
        return parsed[-1]
    return parsed


def pull_calls_per_month():
    """Per advisor × month: total/inbound/outbound call counts + avg/median durations.
    Matches the advisor_phone_metrics_v2.sql schema/conventions but grouped per month."""
    sql = f"""
    with adv_base as (
      select name, cxone_agent_id, pe
      from bi.gusto_employees
      where sub_team in ('Benefits Advising','Customer Advising')
        and current_flag = TRUE and terminated_at is null
    ),
    rd as (
      select distinct
        adv.name,
        to_char(date_trunc('month', ph.conversation_start_date), 'YYYY-MM') as month_key,
        ph.conversation_id,
        ph.sum_voice_ttalkcomplete_secs,
        ph.orig_direction
      from bi.phone_user_metrics ph
      join adv_base adv on ph.user_id::varchar = adv.cxone_agent_id::varchar
      where ph.conversation_start_date between '{WIN_START}' and '{WIN_END}'
    )
    select
      name as advisor_name, month_key,
      count(conversation_id) as total,
      sum(case when orig_direction='inbound' then 1 else 0 end) as inbound,
      sum(case when orig_direction='outbound' then 1 else 0 end) as outbound,
      round(avg(case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as inbound_avg_min,
      round(percentile_cont(0.5) within group (
        order by case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as inbound_median_min,
      round(avg(case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as outbound_avg_min,
      round(percentile_cont(0.5) within group (
        order by case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as outbound_median_min
    from rd
    group by 1, 2
    order by advisor_name, month_key
    """
    rows = run_sql(sql)
    out = defaultdict(dict)
    for r in rows:
        name = (r.get("ADVISOR_NAME") or "").strip()
        mk = r.get("MONTH_KEY")
        if not name or not mk:
            continue
        out[name][mk] = {
            "inbound": int(r.get("INBOUND") or 0),
            "outbound": int(r.get("OUTBOUND") or 0),
            "total": int(r.get("TOTAL") or 0),
            "inboundAvgMin": float(r["INBOUND_AVG_MIN"]) if r.get("INBOUND_AVG_MIN") is not None else None,
            "inboundMedianMin": float(r["INBOUND_MEDIAN_MIN"]) if r.get("INBOUND_MEDIAN_MIN") is not None else None,
            "outboundAvgMin": float(r["OUTBOUND_AVG_MIN"]) if r.get("OUTBOUND_AVG_MIN") is not None else None,
            "outboundMedianMin": float(r["OUTBOUND_MEDIAN_MIN"]) if r.get("OUTBOUND_MEDIAN_MIN") is not None else None,
        }
    return dict(out)


def pull_levelai_channels_per_month():
    """Per advisor × month × channel: count of Level AI QA'd evaluations."""
    sql = f"""
    with src as (
      select
        convert_timezone('UTC','America/Denver', a.conversation_ts)::date as convo_dt,
        to_char(date_trunc('month',
          convert_timezone('UTC','America/Denver', a.conversation_ts)), 'YYYY-MM') as month_key,
        ee.name as advisor_name,
        lower(a.channel_name) as channel
      from bi.fct_level_ai_conversation_asr_log a
      left join bi.cases b on a.case_number = b.casenumber
      join bi.gusto_employees ee
        on convert_timezone('UTC','America/Denver', a.conversation_ts)::date
             between ee.effect_start_dt and ee.effect_end_dt
       and a.user_email = ee.email
       and ee.team in ('Benefits Operations', 'Benefits Advising', 'Benefits Support', 'Benefits Onboarding')
      where a.qa_score is not null
        and nvl(b.record_type_name, 'Call') in (
              'Benefits Renewal Case', 'Benefits BYB', 'Benefits New Plan Case',
              'MF NHE', 'MF Member/Group Updates', 'Call'
            )
        and convert_timezone('UTC','America/Denver', a.conversation_ts)::date >= '{WIN_START}'
        and convert_timezone('UTC','America/Denver', a.conversation_ts)::date <= '{WIN_END}'
    )
    select advisor_name, month_key, channel, count(*) as n
    from src
    where advisor_name is not null
    group by 1, 2, 3
    order by advisor_name, month_key, channel
    """
    rows = run_sql(sql)
    out = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        name = (r.get("ADVISOR_NAME") or "").strip()
        mk = r.get("MONTH_KEY")
        ch = (r.get("CHANNEL") or "").strip().lower()
        n = int(r.get("N") or 0)
        if not name or not mk or not ch:
            continue
        out[name][mk][ch] = n
    return {n: dict(m) for n, m in out.items()}


def main():
    print("[1/2] Pulling calls per month from Snowflake ...", file=sys.stderr)
    calls = pull_calls_per_month()
    print(f"  → {len(calls)} advisors with call data", file=sys.stderr)

    print("[2/2] Pulling Level AI channels per month from Snowflake ...", file=sys.stderr)
    levelai = pull_levelai_channels_per_month()
    print(f"  → {len(levelai)} advisors with QA'd conversations", file=sys.stderr)

    out_path = os.path.join(HERE, "v11_period_data.json")
    with open(out_path, "w") as f:
        json.dump({"callsByMo": calls, "levelaiChannelsByMo": levelai}, f, indent=1)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
