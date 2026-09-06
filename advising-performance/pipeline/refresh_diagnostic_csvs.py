#!/usr/bin/env python3
"""Re-pull the CSAT + In-App Sentiment CSVs from Snowflake.

Runs the same queries used by the source dashboards (benops_csat_surveys.sql,
benops_inapp_sentiment.sql) and writes fresh CSVs into queries/. Date window
matches v11's active months (2025-01-01 through latest month-end of 2026-05-31).
"""
import os, sys, subprocess
import datetime as _dt
from pathlib import Path

HERE = Path(__file__).parent
SNOW = os.path.expanduser("~/.local/bin/snow")
WIN_START = "2025-01-01"
# Auto-advance to today (or PERF_END) so the current partial month is captured.
WIN_END = os.environ.get("PERF_END") or _dt.date.today().isoformat()

QTAG = ('{"qtag":{"version":"1.1.0","source":{"claude_code":'
        '{"username":"serene-sleepy-ramanujan","hostname":"claude",'
        '"source":"query-snowflake-skill"}}}}')


def run_to_csv(sql_text, out_path):
    full = f"ALTER SESSION SET QUERY_TAG = '{QTAG}';\n{sql_text}"
    cmd = [SNOW, "sql", "-c", "default", "-q", full, "--format", "CSV",
           "--enable-templating", "NONE", "--warehouse", "GUSTIE_ADHOC_WH"]
    print(f"[pull] -> {out_path.name}", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print("STDERR:", proc.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"snow failed ({proc.returncode})")
    # Snowflake CSV mode outputs "Statement executed successfully" first then the rows.
    # Split on the first newline-blank-newline (which separates the two result sets).
    out = proc.stdout
    parts = out.split("\n\n", 1)
    if len(parts) == 2 and "Statement executed" in parts[0]:
        csv_text = parts[1]
    else:
        csv_text = out
    with open(out_path, "w") as f:
        f.write(csv_text)
    # Count lines
    n = csv_text.count("\n")
    print(f"  → {n:,} lines", file=sys.stderr)


def main():
    # CSAT
    csat_sql = (HERE / "queries" / "benops_csat_surveys.sql").read_text()
    csat_sql = csat_sql.replace("{{Date Start}}", WIN_START).replace("{{Date End}}", WIN_END)
    out_csat = HERE / "queries" / f"csat_data_{WIN_START}_to_{WIN_END}.csv"
    run_to_csv(csat_sql, out_csat)

    # In-App Sentiment
    inapp_sql = (HERE / "queries" / "benops_inapp_sentiment.sql").read_text()
    inapp_sql = (inapp_sql
                 .replace("{{survey_start_date}}", WIN_START)
                 .replace("{{survey_end_date}}", WIN_END)
                 .replace("{{workflow_status}}", "'Completed','Abandoned'"))
    out_inapp = HERE / "queries" / f"inapp_data_{WIN_START}_to_{WIN_END}.csv"
    run_to_csv(inapp_sql, out_inapp)

    print(f"\n[done] CSVs through {WIN_END}", file=sys.stderr)


if __name__ == "__main__":
    main()
