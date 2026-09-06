#!/usr/bin/env python3
"""Inject the Excel export into the built NPR (NP & Renewal Onboarding) Performance v6 HTML.

Mirrors add_bo_export.py: reuses the same data-agnostic export functions
(bo_export_funcs.html) + button/dock (bo_export_btn.html), and builds the
__EXPORT_DATA__ payload FROM THE DATA ALREADY EMBEDDED in the target HTML
(the `var DATA=` object) — so it never triggers a data refresh.

Run standalone:   python3 add_npr_export.py [path-to-built-v6-html]
Call after gen8.py in the NPR refresh so the export survives every rebuild
(gen8 does NOT emit the export, which is why it was lost on rebuild).
"""
import sys, os, re, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "oa_dash", "np_renewal_onboarding_performance_dashboard_v6.html")

def rh(v):  # round-half-up to match JS Math.round
    return int(math.floor(v + 0.5))
def pct(m, t):
    m = m or 0; t = t or 0
    return f"{rh(100.0*m/t)}% ({int(m)}/{int(t)})" if t else "—"
def qual(sm, ct):
    sm = sm or 0; ct = ct or 0
    return f"{sm/ct:.1f} (n={int(ct)})" if ct else "—"
def ratio(sm, dn):
    sm = sm or 0; dn = dn or 0
    return f"{sm/dn:.2f} ({int(sm)}/{int(dn)})" if dn else "—"

FIELDS = ["av_s","av_d","ab_n","ab_d","ts_n","ts_d","oa_n","oa_d","qa_s","qa_n",
          "tnp_s","tnp_d","trn_s","trn_d","nc_n","nc_d","cs_s","cs_n","em_n","em_d","ma_n","ma_d"]

def extract_DATA(html):
    i = html.find("var DATA=")
    j = html.find("{", i); depth = 0; k = j
    while k < len(html):
        ch = html[k]
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: break
        k += 1
    return json.loads(html[j:k+1])

def build_payload(DATA):
    months = DATA.get("months", [])
    ics, ic_order, month_rows = {}, [], []

    def csl(x): return f"[{x.get('d','')} · {x.get('s','')}★] {x.get('c','')}"

    for ic in DATA.get("ics", []):
        name = ic["name"]; pe = ic.get("manager", "")
        mm = ic.get("months", {}) or {}
        # ---- summary totals over all months ----
        tot = {f: 0 for f in FIELDS}
        for mo in months:
            c = mm.get(mo) or {}
            for f in FIELDS:
                v = c.get(f)
                if v: tot[f] += v
        scored = [
            pct(tot["av_s"], tot["av_d"]),                                   # Phone Avail
            pct(tot["ab_n"], tot["ab_d"]),                                   # Abandon (rate)
            pct(tot["ts_n"], tot["ts_d"]),                                   # Ticket SLA
            pct(tot["oa_n"], tot["oa_d"]),                                   # BO Status (OA Held)
            qual(tot["qa_s"], tot["qa_n"]),                                  # Level AI QA
            "NP " + ratio(tot["tnp_s"], tot["tnp_d"]) + " · RN " + ratio(tot["trn_s"], tot["trn_d"]),  # Ticket Rate
            pct(tot["nc_n"], tot["nc_d"]),                                   # NP Cancel
        ]
        diag = [ qual(tot["cs_s"], tot["cs_n"]), pct(tot["em_n"], tot["em_d"]), pct(tot["ma_n"], tot["ma_d"]) ]
        cc = sorted(ic.get("comments", []) or [], key=lambda x: x.get("d", ""), reverse=True)
        detail = [ "\n".join(csl(x) for x in cc) ]
        ics[name.lower()] = {"ic": name, "id": [name, pe], "scored": scored, "diag": diag, "detail": detail}
        ic_order.append(name)
        # ---- per-month rows ----
        for mo in months:
            c = mm.get(mo) or {}
            ccm = [x for x in cc if str(x.get("d", ""))[:7] == mo]
            month_rows.append([name, mo,
                pct(c.get("av_s"), c.get("av_d")), pct(c.get("ab_n"), c.get("ab_d")),
                pct(c.get("ts_n"), c.get("ts_d")), pct(c.get("oa_n"), c.get("oa_d")),
                qual(c.get("qa_s"), c.get("qa_n")),
                "NP " + ratio(c.get("tnp_s"), c.get("tnp_d")) + " · RN " + ratio(c.get("trn_s"), c.get("trn_d")),
                pct(c.get("nc_n"), c.get("nc_d")),
                qual(c.get("cs_s"), c.get("cs_n")), pct(c.get("em_n"), c.get("em_d")), pct(c.get("ma_n"), c.get("ma_d")),
                "\n".join(csl(x) for x in ccm)])

    return {
        "filename": "NPR_Performance_Export.xlsx", "team": "NPR",
        "readme": [
            "NP & Renewal Onboarding Performance — Excel Export",
            "Every scored metric shows its value AND underlying counts; diagnostics are inline; CSAT comments appear in both the Current-view and IC × Month tabs.",
            "",
            "Metric cells: value % (numerator / denominator). Level AI QA / CSAT = avg (n responses). Ticket Rate = tickets per fulfilled BO, by order type (NP · RN).",
            "Diagnostics (not scored): CSAT = avg (n responses), Email SLA = within/answered %, Maestro = complete/eligible %.",
            "'IC Summary (current view)' respects the on-screen filters; 'IC × Month' lists every month for the filtered ICs.",
            "Generated from the live dashboard data."],
        "id_cols": ["IC", "PE"],
        "scored_headers": ["Phone Avail", "Abandon", "Ticket SLA", "BO Status (OA Held)", "Level AI QA", "Ticket Rate", "NP Cancel"],
        "diag_headers": ["CSAT", "Email SLA", "Maestro"],
        "detail_headers_summary": ["CSAT comments (all)"],
        "detail_headers_month": ["CSAT comments (mo)"],
        "ics": ics, "ic_order": ic_order, "month_rows": month_rows}

def inject(html_path=DEFAULT):
    s = open(html_path, encoding="utf-8").read()
    # idempotent: strip any prior injected export block (wrapped in markers)
    s = re.sub(r'<!--NPR_EXPORT_START-->.*?<!--NPR_EXPORT_END-->', '', s, flags=re.S)
    DATA = extract_DATA(s)
    payload = build_payload(DATA)
    pj = json.dumps(payload, ensure_ascii=False)
    funcs = open(os.path.join(HERE, "bo_export_funcs.html"), encoding="utf-8").read()
    btn   = open(os.path.join(HERE, "bo_export_btn.html"), encoding="utf-8").read()
    block = ("<!--NPR_EXPORT_START-->\n"
             '<script src="https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js"></script>\n'
             '<script id="__EXPORT_DATA__" type="application/json">' + pj + '</script>\n'
             + funcs + "\n" + btn + "\n<!--NPR_EXPORT_END-->")
    pos = s.rfind("</body>")
    if pos < 0: raise SystemExit("no </body> in " + html_path)
    s = s[:pos] + block + "\n" + s[pos:]
    open(html_path, "w", encoding="utf-8").write(s)
    print(f"injected export into {os.path.basename(html_path)}: "
          f"{len(payload['ic_order'])} ICs, {len(payload['month_rows'])} month-rows")

if __name__ == "__main__":
    inject(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
