#!/usr/bin/env python3
"""Take the v11_core_data.json (raw per-advisor × month aggregates from Snowflake)
and rebuild v11's D.advisors + D.icDetail in-place.

Preserves: D.months, D.peMap, D.csatData, D.inappData, D.emailSlaData,
           D.callsByMo, D.levelAiChannelsByMo, D.availData, D.abandonData.
Rebuilds:  D.advisors[*] (per-metric rate dicts),
           D.icDetail[*] (opps, bos, tickets, avail, quality, calls sub-objects).
"""
import json
import os
import re
import datetime as _dt
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
V11 = HERE / "advising_performance_dashboard_v11.html"
CORE = HERE / "v11_core_data.json"

with open(CORE) as f:
    data = json.load(f)
with open(V11) as f:
    html = f.read()

# ── Union-from-data roster (was: carried-forward peMap keys only) ──
# roster = active advisors ∪ any advisor with data in-window, SCOPED to genuine Advising staff via
# data['adv_roster'] (widened employee pull: Benefits/Customer Advising, is_pe=false, ALL statuses,
# + last-known PE). Keys keep the DATA owner_name spelling so metric rows still attach; the
# month-aware auto-uncheck hides months an advisor has no data (departed keep worked-months).
m = re.search(r'"peMap":\s*(\{[^\{\}]*(?:\{[^\}]*\}[^\{\}]*)*\})', html, re.DOTALL)
if not m:
    raise RuntimeError("peMap not found")
old_peMap = json.loads(m.group(1))
_pe_map_data = data.get("pe_map", {})
def _nz(s): return (s or "").strip().lower()
_emp = { _nz(r.get("NAME")): {"status": r.get("STATUS") or "", "mgr": r.get("MANAGER") or ""}
         for r in data.get("adv_roster", []) }
_active = { n for n, d_ in _emp.items() if d_["status"] in ("Active", "On Leave") }
_data_names = {}
for _k in _pe_map_data: _data_names.setdefault(_nz(_k), _k)
for _key in ("ticket_sla", "bo_grain", "level_ai", "opp"):
    for _r in (data.get(_key) or []):
        for _c in ("OWNER_NAME","OWNER","ADVISOR_NAME","TICKET_OWNER_NAME","FULL_NAME"):
            _v = _r.get(_c)
            if _v: _data_names.setdefault(_nz(_v), _v)
_scoped = { sp for nn, sp in _data_names.items() if nn in _emp }
def _keep(n):
    nn = _nz(n)
    if nn in _active: return True
    if nn in _data_names: return True
    if nn in _emp: return False
    return n in old_peMap
roster = sorted({n for n in (set(old_peMap) | _scoped) if _keep(n)})
def _pe_for(n):
    return _pe_map_data.get(n) or _emp.get(_nz(n), {}).get("mgr") or old_peMap.get(n) or "—"
peMap = { n: _pe_for(n) for n in roster }
current_pe = { n: _pe_for(n) for n in roster }
print(f"Roster (union-from-data): {len(roster)} advisors (old curated {len(old_peMap)})")


# ── Build per-advisor × month dicts from the Snowflake rows ──

# erConfirm / rfd / alt + opp byStatus, byRecordType
adv_er = defaultdict(lambda: defaultdict(lambda: {"met":0,"total":0}))
adv_rfd = defaultdict(lambda: defaultdict(lambda: {"met":0,"total":0}))
opps_byStatus = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
opps_byRecordType = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
opps_erConfirm = defaultdict(lambda: defaultdict(lambda: {"touched":0,"met":0,"daysSum":0.0}))
opps_rdp = defaultdict(lambda: defaultdict(lambda: {"touched":0,"met":0,"daysSum":0.0}))
opps_alt = defaultdict(lambda: defaultdict(lambda: {"touched":0,"met":0,"daysSum":0.0}))

for r in data["opp"]:
    name = r["ADVISOR_NAME"]
    mk = r["MONTH_KEY"]
    if name not in peMap or not mk:
        continue
    status = r.get("STATUS") or "Unknown"
    n = int(r.get("N") or 0)
    er_t = int(r.get("ER_TOUCHED") or 0); er_m = int(r.get("ER_MET") or 0); er_d = float(r.get("ER_DAYS_SUM") or 0)
    rdp_t = int(r.get("RDP_TOUCHED") or 0); rdp_m = int(r.get("RDP_MET") or 0); rdp_d = float(r.get("RDP_DAYS_SUM") or 0)
    alt_t = int(r.get("ALT_TOUCHED") or 0); alt_m = int(r.get("ALT_MET") or 0); alt_d = float(r.get("ALT_DAYS_SUM") or 0)
    # ER Confirm metric (per advisor metric)
    adv_er[name][mk]["met"] += er_m
    adv_er[name][mk]["total"] += er_t
    # RFD + Alt SLA combined metric
    adv_rfd[name][mk]["met"] += (rdp_m + alt_m)
    adv_rfd[name][mk]["total"] += (rdp_t + alt_t)
    # icDetail: opps
    opps_byStatus[name][status][mk] += n
    opps_byRecordType[name]["N/A"][mk] += n
    if er_t > 0:
        opps_erConfirm[name][mk]["touched"] += er_t
        opps_erConfirm[name][mk]["met"] += er_m
        opps_erConfirm[name][mk]["daysSum"] += er_d
    if rdp_t > 0:
        opps_rdp[name][mk]["touched"] += rdp_t
        opps_rdp[name][mk]["met"] += rdp_m
        opps_rdp[name][mk]["daysSum"] += rdp_d
    if alt_t > 0:
        opps_alt[name][mk]["touched"] += alt_t
        opps_alt[name][mk]["met"] += alt_m
        opps_alt[name][mk]["daysSum"] += alt_d

# Ticket SLA per advisor × month
adv_tixSla = defaultdict(lambda: defaultdict(lambda: {"met":0,"total":0}))
tickets_asOwner = defaultdict(lambda: {"total": defaultdict(int), "inSla": defaultdict(int)})
for r in data["ticket_sla"]:
    name = r["ADVISOR_NAME"]
    mk = r["MONTH_KEY"]
    if name not in peMap or not mk:
        continue
    total = int(r.get("TOTAL") or 0)
    met = int(r.get("MET") or 0)
    adv_tixSla[name][mk]["met"] += met
    adv_tixSla[name][mk]["total"] += total
    tickets_asOwner[name]["total"][mk] += total
    tickets_asOwner[name]["inSla"][mk] += met

# Apply Ticket SLA <5 ticket guard at the period level
# (Done at render time in the dashboard via cmAll: if total < 5, value becomes null.
#  We just store raw met/total and let the dashboard apply the guard.)

# BO grain: BOs fulfilled / cancelled + Ticket Rate
adv_tixRate = defaultdict(lambda: defaultdict(lambda: {"tix":0,"orders":0}))
bos_fulfilled = defaultdict(lambda: defaultdict(int))
bos_cancelled = defaultdict(lambda: defaultdict(int))
for r in data["bo_grain"]:
    name = r["ADVISOR_NAME"]
    mk = r["MONTH_KEY"]
    if name not in peMap or not mk:
        continue
    ful = int(r.get("FULFILLED") or 0)
    can = int(r.get("CANCELLED") or 0)
    tix = int(r.get("BENADV_TIX_ON_FULFILLED") or 0)
    bos_fulfilled[name][mk] = ful
    bos_cancelled[name][mk] = can
    adv_tixRate[name][mk]["orders"] += ful
    adv_tixRate[name][mk]["tix"] += tix

# Availability
avail_byMo = defaultdict(lambda: defaultdict(lambda: {"eligible":0,"met":0}))
availData_period = defaultdict(lambda: {"eligibleSum":0, "metSum":0})
for r in data["availability"]:
    name = r["ADVISOR_NAME"]
    mk = r["MONTH_KEY"]
    if name not in peMap or not mk:
        continue
    el = int(r.get("ELIGIBLE") or 0)
    me = int(r.get("MET") or 0)
    avail_byMo[name][mk]["eligible"] = el
    avail_byMo[name][mk]["met"] = me
    availData_period[name]["eligibleSum"] += el
    availData_period[name]["metSum"] += me

# D.availData is per-advisor × month {eligible, met} dicts — cmAll() reads it directly
availData = {n: {mk: dict(v) for mk, v in months.items()} for n, months in avail_byMo.items()}

# Abandon per month
abandon_byMo = defaultdict(lambda: defaultdict(lambda: {"inbound":0,"abandonedMod":0}))
abandonData_period = defaultdict(lambda: {"inb":0, "abMod":0})
for r in data["abandon"]:
    name = r["ADVISOR_NAME"]
    mk = r["MONTH_KEY"]
    if name not in peMap or not mk:
        continue
    inb = int(r.get("INBOUND") or 0)
    abm = int(r.get("ABANDONED_MOD") or 0)
    abandon_byMo[name][mk]["inbound"] = inb
    abandon_byMo[name][mk]["abandonedMod"] = abm
    abandonData_period[name]["inb"] += inb
    abandonData_period[name]["abMod"] += abm

# D.abandonData is per-advisor × month {inbound, abandonedMod} dicts — cmAll() reads it directly
abandonData = {n: {mk: dict(v) for mk, v in months.items()} for n, months in abandon_byMo.items()}

# Level AI per advisor × month
adv_quality = defaultdict(lambda: defaultdict(lambda: {"sum":0.0,"count":0}))
quality_evalsByMo = defaultdict(lambda: defaultdict(int))
quality_scoreSumByMo = defaultdict(lambda: defaultdict(float))
for r in data["level_ai"]:
    name = r["ADVISOR_NAME"]
    mk = r["MONTH_KEY"]
    if name not in peMap or not mk:
        continue
    n = int(r.get("EVALS") or 0)
    s = float(r.get("SCORE_SUM_PCT") or 0)
    adv_quality[name][mk]["sum"] += s
    adv_quality[name][mk]["count"] += n
    quality_evalsByMo[name][mk] = n
    quality_scoreSumByMo[name][mk] = s


# Filter per-month dicts to the active window (the source queries can return
# months outside our window, e.g., BOs with historical first_fulfilled timestamps).
# Window auto-advances: fixed start (2026-01) through the current pull month, so the
# current (partial) month is included automatically — no monthly hand-edit needed.
_WIN_START = (2026, 1)
_PULL_END = _dt.date.fromisoformat(os.environ.get("PERF_END") or _dt.date.today().isoformat())
ACTIVE_MONTHS = set()
_yy, _mm = _WIN_START
while (_yy, _mm) <= (_PULL_END.year, _PULL_END.month):
    ACTIVE_MONTHS.add(f"{_yy:04d}-{_mm:02d}")
    _mm += 1
    if _mm > 12:
        _mm = 1
        _yy += 1
def trim(d):
    return {mk: v for mk, v in d.items() if mk in ACTIVE_MONTHS}

# ── Assemble new D.advisors[i] objects ──
new_advisors = []
for name in sorted(roster):
    pe = current_pe[name]
    adv = {"name": name, "pe": pe,
           "erConfirm": trim(dict(adv_er.get(name, {}))),
           "rfd": trim(dict(adv_rfd.get(name, {}))),
           "tixSla": trim(dict(adv_tixSla.get(name, {}))),
           "tixRate": trim(dict(adv_tixRate.get(name, {}))),
           "quality": {mk: {"sum": round(v["sum"]*100)/100, "count": v["count"]}
                       for mk, v in adv_quality.get(name, {}).items() if mk in ACTIVE_MONTHS}}
    for k in ["erConfirm","rfd","tixSla","tixRate","quality"]:
        if not adv[k]:
            adv[k] = {}
    new_advisors.append(adv)

# parity tighten: drop former advisors with no in-window scored data (match NPR/Broker in-window gate)
_before = len(new_advisors)
new_advisors = [a for a in new_advisors
                if (_nz(a["name"]) in _active)
                or any(a.get(k) for k in ("erConfirm", "rfd", "tixSla", "tixRate", "quality"))]
_kept = {a["name"] for a in new_advisors}
roster = [n for n in roster if n in _kept]
peMap = {n: peMap[n] for n in _kept}
current_pe = {n: current_pe[n] for n in _kept}
print(f"parity tighten: dropped {_before - len(new_advisors)} former advisor(s) with no in-window data")

assert all(a["pe"] == current_pe[a["name"]] for a in new_advisors), \
    "advisors[*].pe must equal current_pe (current-PE consistency guard)"

# Also trim icDetail per-month subsections to active months
def trim_byMo(per_advisor_dict):
    return {n: {mk: v for mk, v in months.items() if mk in ACTIVE_MONTHS} for n, months in per_advisor_dict.items()}
opps_byStatus = {n: {s: {mk: v for mk, v in months.items() if mk in ACTIVE_MONTHS} for s, months in statuses.items()} for n, statuses in opps_byStatus.items()}
opps_byRecordType = {n: {s: {mk: v for mk, v in months.items() if mk in ACTIVE_MONTHS} for s, months in statuses.items()} for n, statuses in opps_byRecordType.items()}
opps_erConfirm = trim_byMo(opps_erConfirm)
opps_rdp = trim_byMo(opps_rdp)
opps_alt = trim_byMo(opps_alt)
bos_fulfilled = trim_byMo(bos_fulfilled)
bos_cancelled = trim_byMo(bos_cancelled)
for n in tickets_asOwner:
    tickets_asOwner[n]["total"] = {mk: v for mk, v in tickets_asOwner[n]["total"].items() if mk in ACTIVE_MONTHS}
    tickets_asOwner[n]["inSla"] = {mk: v for mk, v in tickets_asOwner[n]["inSla"].items() if mk in ACTIVE_MONTHS}
avail_byMo = trim_byMo(avail_byMo)
abandon_byMo = trim_byMo(abandon_byMo)
quality_evalsByMo = trim_byMo(quality_evalsByMo)
quality_scoreSumByMo = trim_byMo(quality_scoreSumByMo)
availData = trim_byMo(availData) if availData else {}
abandonData = trim_byMo(abandonData) if abandonData else {}

# ── Assemble new icDetail[name] ──
def dd_to_d(dd): return {k: dict(v) if hasattr(v, "items") else v for k,v in dd.items()}

new_icDetail = {}
for name in roster:
    rec = {
        "opps": {
            "byStatus": {k: dict(v) for k,v in opps_byStatus.get(name, {}).items()},
            "byRecordType": {k: dict(v) for k,v in opps_byRecordType.get(name, {}).items()},
            "erConfirm": {mk: dict(v) for mk,v in opps_erConfirm.get(name, {}).items()},
            "rdp": {mk: dict(v) for mk,v in opps_rdp.get(name, {}).items()},
            "alt": {mk: dict(v) for mk,v in opps_alt.get(name, {}).items()},
        },
        "bos": {
            "fulfilled": dict(bos_fulfilled.get(name, {})),
            "cancelled": dict(bos_cancelled.get(name, {})),
        },
        "tickets": {
            "asOwner": {
                "total": dict(tickets_asOwner.get(name, {"total":{}})["total"]),
                "inSla": dict(tickets_asOwner.get(name, {"inSla":{}})["inSla"]),
            },
        },
        "avail": {"byMo": {mk: dict(v) for mk,v in avail_byMo.get(name, {}).items()}},
        "calls": {"byMo": {mk: dict(v) for mk,v in abandon_byMo.get(name, {}).items()}},
        "quality": {
            "evalsByMo": dict(quality_evalsByMo.get(name, {})),
            "scoreSumByMo": {mk: round(v*100)/100 for mk,v in quality_scoreSumByMo.get(name, {}).items()},
        },
    }
    new_icDetail[name] = rec


# ── Update v11 HTML: replace D.advisors, D.icDetail, D.availData, D.abandonData ──
def jdump(obj): return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

def replace_d_field(html, key, new_value_str):
    """Replace the contents of D's "key" field. Handles {} and [] values."""
    m = re.search(r'"' + key + r'":\s*', html)
    if not m:
        # Insert before the closing } of D
        anchor = re.search(r'"peMap":', html)
        if not anchor:
            raise RuntimeError(f"Cannot find insertion point for {key}")
        # Insert before peMap
        insert_at = anchor.start()
        return html[:insert_at] + '"' + key + '":' + new_value_str + ',' + html[insert_at:]
    start = m.end()
    open_ch = html[start]
    if open_ch not in "{[":
        raise RuntimeError(f"Unexpected value start for {key}: {open_ch!r}")
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str = False; str_ch = None; escaped = False
    i = start
    while i < len(html):
        ch = html[i]
        if escaped: escaped = False
        elif ch == "\\": escaped = True
        elif in_str:
            if ch == str_ch: in_str = False
        elif ch in ('"', "'"):
            in_str = True; str_ch = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    return html[:start] + new_value_str + html[end:]

print(f"  advisors with metric data: {sum(1 for a in new_advisors if a['erConfirm'] or a['rfd'] or a['tixSla'] or a['tixRate'] or a['quality'])}/{len(new_advisors)}")

html = replace_d_field(html, "advisors", jdump(new_advisors))
html = replace_d_field(html, "icDetail", jdump(new_icDetail))
html = replace_d_field(html, "availData", jdump(availData))
html = replace_d_field(html, "abandonData", jdump(abandonData))

# ── Refresh PE to CURRENT (data-driven), keeping the curated roster keys ──
# pe_map = current PE per advisor from pull_pe_map(); fall back to the existing
# manual peMap value for rostered advisors with no opp data (e.g. zero-volume).
if _pe_map_data:
    changed = sum(1 for n in peMap if current_pe[n] != peMap[n])
    html = replace_d_field(html, "peMap", jdump(current_pe))
    print(f"  peMap + advisors[*].pe refreshed to current PE: {changed} value(s) changed, {len(current_pe)} rostered")
else:
    print("  peMap: no pe_map in data — kept existing (run pull_v11 to enable current-PE)")

# ── Advance D.months to the active window so the current month displays ──
_months_json = "[" + ",".join(f'"{mk}"' for mk in sorted(ACTIVE_MONTHS)) + "]"
html, _n_mo = re.subn(r'"months":\s*\[[^\]]*\]', '"months":' + _months_json, html, count=1)
if _n_mo != 1:
    raise RuntimeError("D.months literal not found to update")
print(f"  D.months -> {sorted(ACTIVE_MONTHS)}")

# ── Footer dates (build-time literals; idempotent across reruns) ──
# Snowflake data lags ~1 day, so "data as of" = pull-end minus 1 day; "published" = pull-end (today).
_MONTHS_EN = ["January","February","March","April","May","June","July",
              "August","September","October","November","December"]
def _long(d):
    return f"{_MONTHS_EN[d.month-1]} {d.day}, {d.year}"
DATA_AS_OF = _long(_PULL_END - _dt.timedelta(days=1))
PUBLISHED_ON = _long(_PULL_END)

# Footer labels -> clear wording
html = html.replace("<b>Data through</b>", "<b>Data updated as of</b>")
html = html.replace("<b>Refreshed</b>", "<b>Last published</b>")

# fill(): bake literal dates. Scoped by the trailing `var re=` which exists only in
# fill(); matches both the original computed form and a prior literal form (idempotent).
html, _n_fill = re.subn(
    r'(\n\s*)var dt="[^"]*";(?:\s*\n\s*if\(ms\.length\)\{[^\n]*\})?(\s*\n\s*)var re="[^"]*";(?:\s*if\(re\.indexOf\("__"\)>=0\) re="";)?',
    lambda mo: f'{mo.group(1)}var dt="{DATA_AS_OF}";{mo.group(2)}var re="{PUBLISHED_ON}";',
    html, count=1)
if _n_fill != 1:
    raise RuntimeError("footer fill() dt/re block not found to update")

# nowStr(): per-advisor report footer — match original or prior-literal form
_nowstr_new = f'return "Data updated as of {DATA_AS_OF} · last published {PUBLISHED_ON}";'
html = re.sub(r'return "Data through "\+dt\+"[^"]*";', _nowstr_new, html, count=1)
html = re.sub(r'return "Data updated as of [^"]*";', _nowstr_new, html, count=1)
print(f"  footer -> data as of {DATA_AS_OF}; last published {PUBLISHED_ON}")

with open(V11, "w") as f:
    f.write(html)
print(f"\nWrote {V11}")
print(f"  size: {len(html):,} chars")
