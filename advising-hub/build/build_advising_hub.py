#!/usr/bin/env python3
"""Build the self-contained Advising Hub dashboard (v-next, 3 tabs, all cohorts).
Three tabs — Open / Pending Fulfillment / Closed — over all ~15,239 opps.
Reuses the BenOps design system (indigo #4f46e5 + coral), multi-select checkbox
filters, cohort picker, synced horizontal scrollbars, sortable columns, row
drill-down, alpha tag. Data embedded. SHOW-ALL-FIELDS policy: blank = "—" in the
grid AND the drill; no empty rows/sections are hidden."""
import json, os, re, html as _html

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "_renewal_vnext", "advising_vnext_data.json")
GUIDE_PATH = os.path.join(HERE, "Advising_Hub_README.md")
OUT  = os.path.join(HERE, "advising_hub_vnext.html")

data = json.load(open(DATA_PATH))
n_opps = len(data)
n_lines = sum(len(o.get("lines") or []) for o in data)
data_json = json.dumps(data, separators=(",", ":"))
data_json = data_json.replace("</", "<\\/")

def md_to_html(md):
    """Minimal Markdown -> HTML for the Guide pane: headings, bold, inline code,
    bullet lists, horizontal rules, and paragraphs. Escapes HTML first."""
    def inline(t):
        t = _html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t
    out, lines, i = [], md.splitlines(), 0
    para, in_ul = [], False
    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para).strip()) + "</p>")
            para = []
    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>"); in_ul = False
    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()
        if not s:
            flush_para(); close_ul()
        elif re.match(r"^---+$", s):
            flush_para(); close_ul(); out.append("<hr>")
        elif s.startswith("### "):
            flush_para(); close_ul(); out.append("<h3>" + inline(s[4:]) + "</h3>")
        elif s.startswith("## "):
            flush_para(); close_ul(); out.append("<h2>" + inline(s[3:]) + "</h2>")
        elif s.startswith("# "):
            flush_para(); close_ul(); out.append("<h1>" + inline(s[2:]) + "</h1>")
        elif re.match(r"^[-*]\s+", s):
            flush_para()
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append("<li>" + inline(re.sub(r"^[-*]\s+", "", s)) + "</li>")
        else:
            if in_ul: close_ul()
            para.append(s)
        i += 1
    flush_para(); close_ul()
    return "\n".join(out)

guide_html = md_to_html(open(GUIDE_PATH, encoding="utf-8").read()) if os.path.exists(GUIDE_PATH) \
    else "<p>Guide unavailable.</p>"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Benefits Advising Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  color-scheme:light;
  --teal:#4f46e5; --teal-dk:#3730a3; --teal-tint:#e0e7ff; --teal-050:#eef0fe;
  --coral:#F45D48; --coral-dk:#993C1D; --coral-20:#fde3de;
  --ink:#222525; --g6:#6b7280; --g5:#9ca3af; --g4:#e5e7eb; --g3:#f3f4f6; --g2:#f9fafb;
  --gold:#b8860b; --cream:#FFF4E0; --cream-2:#faeeda; --purple:#4f46e5; --green:#1D9E75;
  --slate:#334155; --slate-chip:#64748b; --plum:#7c3a6e;
  --bg:#F7F4F2; --card:#FFFFFF; --line:#e5e7eb;
  --ui:"Bricolage Grotesque","Segoe UI",-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.5 var(--ui)}
a{color:var(--teal);text-decoration:none}
a:hover{text-decoration:underline}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:12px}
.wrap{padding:0 22px 60px}
.head{position:sticky;top:0;z-index:40;background:var(--card);border-bottom:1px solid var(--line);
  display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:14px 0;margin:0 0 4px}
.head .brand{font:700 26px/1 var(--ui);letter-spacing:-.01em}
.head .verbadge{display:inline-block;vertical-align:middle;margin-left:9px;font:700 9.5px var(--ui);letter-spacing:.1em;text-transform:uppercase;color:var(--teal);background:#eef2ff;border:1px solid #c7d2fe;border-radius:5px;padding:2px 7px;position:relative;top:-3px}
.head .brand b{color:var(--teal)}
.head .sub{font-size:12px;color:var(--g6);margin-top:5px}
.chip.cohort{font:600 12px var(--ui);background:var(--teal-tint);border:1px solid #c7d2fe;color:var(--teal-dk);
  padding:6px 12px;border-radius:999px;white-space:nowrap}
.head .spacer{flex:1}
.btn{font:600 12.5px var(--ui);padding:8px 14px;border-radius:9px;border:1px solid var(--teal);
  background:var(--card);color:var(--teal);cursor:pointer;white-space:nowrap}
.btn:hover{background:var(--teal-050)}
.btn.sm{padding:6px 11px;font-size:12px}
.btn.ghost{border-color:var(--g4);color:var(--ink)}
.btn.ghost:hover{background:var(--g3)}
/* tabs */
.tabs{display:flex;gap:2px;margin:12px 0 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tab{font:600 13px var(--ui);padding:10px 15px;border:1px solid transparent;border-bottom:none;
  border-radius:9px 9px 0 0;background:transparent;color:var(--g6);cursor:pointer;margin-bottom:-1px}
.tab:hover{color:var(--ink);background:var(--teal-050)}
.tab.on{background:var(--card);border-color:var(--line);color:var(--ink)}
.tab.on::after{content:"";display:block;height:2px;background:var(--teal);margin:9px -15px -1px}
.tab .cnt{font:700 10.5px var(--mono);margin-left:7px;color:var(--g5)}
.tab.on .cnt{color:var(--teal)}
.pane{display:none}
.pane.on{display:block}
/* kpis */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(172px,1fr));gap:12px;margin:4px 0 16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.kpi .lbl{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--g6);font-weight:600}
.kpi .val{font:600 28px/1.05 var(--ui);margin-top:7px;font-feature-settings:"tnum"}
.kpi .val.mono{font-family:var(--mono);font-weight:600;font-size:25px}
.kpi .sub2{font-size:11.5px;color:var(--g6);margin-top:4px}
.kpi.accent{background:var(--coral-20);border-color:#f6c9c1}
.kpi.accent .val{color:var(--coral-dk)}
.kpi.tealk{background:var(--teal-tint);border-color:#c7d2fe}
.kpi.tealk .val{color:var(--teal-dk)}
/* controls */
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;margin-bottom:14px}
.fld{display:flex;flex-direction:column;gap:5px}
.fld label{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--g6);font-weight:600}
select,input[type=text]{font:13px var(--ui);padding:8px 10px;border:1px solid var(--line);
  border-radius:9px;background:var(--card);color:var(--ink);min-width:150px}
input[type=text]{min-width:230px}
.spacer{flex:1}
/* multi-select checkbox dropdowns */
.md{position:relative;display:flex;flex-direction:column;gap:5px}
.md>label{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--g6);font-weight:600}
.md-trig{display:flex;align-items:center;gap:8px;min-width:150px;padding:8px 10px;border:1px solid var(--line);
  border-radius:9px;background:var(--card);color:var(--ink);font:13px var(--ui);cursor:pointer}
.md.md-active .md-trig{border-color:var(--teal);background:var(--teal-050)}
.md-trig .md-sum{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.md-trig .md-car{font-size:10px;color:var(--teal)}
.md-pop{position:absolute;top:100%;left:0;z-index:50;margin-top:4px;min-width:210px;max-width:290px;
  background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.13);
  max-height:360px;display:flex;flex-direction:column;overflow:hidden}
.md-actions{display:flex;gap:6px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--line);background:var(--g2)}
.md-btn{font:600 10.5px var(--ui);padding:3px 11px;border-radius:5px;border:1px solid var(--line);
  background:var(--card);color:var(--g6);cursor:pointer}
.md-btn:hover{background:var(--g3)}
.md-btn.md-all.on{background:var(--teal);border-color:var(--teal);color:#fff}
.md-btn.md-none.on{background:var(--coral);border-color:var(--coral);color:#fff}
.md-count{margin-left:auto;font:600 10.5px var(--mono);color:var(--g6)}
.md-searchwrap{padding:6px 10px;border-bottom:1px solid var(--line)}
.md-pop .md-search{width:100%;min-width:0;font:12px var(--ui);padding:5px 8px;border:1px solid var(--line);
  border-radius:6px;background:var(--card);color:var(--ink)}
.md-pop .md-search:focus{outline:none;border-color:var(--teal)}
.md-list{overflow-y:auto;flex:1}
.md-grp{font:700 9px var(--ui);letter-spacing:.05em;text-transform:uppercase;color:var(--teal-dk);
  background:var(--teal-050);border-bottom:1px solid var(--teal-tint);padding:4px 10px}
.md-row{display:flex;align-items:center;gap:7px;padding:5px 10px;font-size:12px;cursor:pointer;border-bottom:1px solid var(--g3)}
.md-row:hover{background:var(--teal-050)}
.md-row input{accent-color:var(--teal);margin:0;flex:none}
.md-row .md-rl{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.md-row .md-ck{font-size:10px;color:var(--teal);font-weight:700}
.md-empty{padding:12px 10px;font-size:11.5px;color:var(--g6);text-align:center}
/* table */
.tbltop{overflow-x:auto;overflow-y:hidden;height:14px;background:var(--card);border:1px solid var(--line);
  border-bottom:none;border-radius:12px 12px 0 0}
.tbltop-inner{height:1px}
.tblwrap{background:var(--card);border:1px solid var(--line);border-radius:0 0 12px 12px;overflow-x:auto;overflow-y:auto;max-height:74vh}
.tbltop,.tblwrap{scrollbar-width:thin;scrollbar-color:var(--g5) var(--g3)}
.tbltop::-webkit-scrollbar,.tblwrap::-webkit-scrollbar{height:12px;width:12px}
.tbltop::-webkit-scrollbar-track,.tblwrap::-webkit-scrollbar-track{background:var(--g3);border-radius:6px}
.tbltop::-webkit-scrollbar-thumb,.tblwrap::-webkit-scrollbar-thumb{background:var(--g5);border-radius:6px;border:2px solid var(--card)}
.tbltop::-webkit-scrollbar-thumb:hover,.tblwrap::-webkit-scrollbar-thumb:hover{background:var(--slate-chip)}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px}
thead th{position:sticky;background:var(--card);z-index:3}
tr.grp th{top:0;height:26px;color:#fff;font:700 9.5px var(--ui);letter-spacing:.1em;text-transform:uppercase;
  padding:5px 9px;border:none;text-align:left;white-space:nowrap}
tr.grp th.g-customer{background:var(--slate)}
tr.grp th.g-queue{background:var(--slate-chip)}
tr.grp th.g-general{background:var(--teal)}
tr.grp th.g-line{background:var(--teal)}
tr.grp th.g-flags{background:var(--coral)}
tr.grp th.g-contact{background:#3f6fa3}
tr.grp th.g-sentiment{background:var(--green)}
tr.grp th.g-contact{background:var(--teal-dk)}
tr.grp th.g-rec{background:var(--gold)}
tr.grp th.g-closed{background:var(--coral-dk)}
tr.grp th.g-bo{background:var(--plum)}
th.pin,td.pin{position:sticky;background:var(--card);z-index:2}
tr.cols th.pin{z-index:6}
tr.grp th.pin{z-index:7}
tr.row:hover td.pin{background:var(--teal-050)}
tr.row.open td.pin{background:var(--teal-tint)}
td.pin.shadow,th.pin.shadow{box-shadow:6px 0 6px -4px rgba(0,0,0,.10)}
tr.cols th{top:26px;text-align:left;font:700 9.5px var(--ui);letter-spacing:.06em;text-transform:uppercase;
  color:var(--g6);padding:9px 9px;border-bottom:1.5px solid var(--ink);white-space:nowrap;cursor:pointer;user-select:none}
tr.cols th:hover{color:var(--teal)}
tr.cols th.g-line{color:var(--teal-dk);background:var(--teal-050)}
td{padding:8px 9px;border-bottom:1px solid var(--g3);vertical-align:middle;white-space:nowrap}
td.g-line{background:var(--teal-050)}
tr.row:hover td{background:var(--teal-050);cursor:pointer}
tr.row:hover td.g-line{background:#dbe1ff}
tr.row.open td{background:var(--teal-tint)}
.co{max-width:230px;display:flex;align-items:center;gap:6px}
.co .cn{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.co .expand{color:var(--teal);font-weight:700;cursor:pointer;display:inline-block;flex-shrink:0}
.co .icons{display:inline-flex;gap:2px;flex-shrink:0}
.co .ic{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;color:var(--g5);border-radius:4px;transition:color .12s ease,background .12s ease}
.co a.ic:hover{color:var(--teal);background:var(--teal-050)}
.co .ic.off{opacity:.32;cursor:default}
.co .ic svg{display:block;width:14px;height:14px;stroke-width:1.6}
.chip{display:inline-block;padding:3px 8px;border-radius:999px;background:var(--g3);font-size:11px;white-space:nowrap;color:var(--ink)}
.chip.stage{background:var(--teal-tint);color:var(--teal-dk)}
.chip.won{background:#d8f3e8;color:var(--green)}
.chip.lost{background:var(--coral-20);color:var(--coral-dk)}
.chip.arch{background:var(--g3);color:var(--g5);font-weight:600;font-style:italic}
.tier{display:inline-block;min-width:26px;text-align:center;padding:3px 7px;border-radius:6px;
  font:700 11px var(--mono);letter-spacing:.02em}
.tier.t1{background:var(--coral);color:#fff}
.tier.t2{background:var(--teal);color:#fff}
.tier.t3{background:var(--gold);color:#fff}
.tier.t4{background:var(--teal);color:#fff}
.tier.t5{background:var(--slate-chip);color:#fff}
.rsc{display:inline-block;min-width:20px;text-align:center;padding:2px 7px;border-radius:6px;
  font:700 10.5px var(--mono);letter-spacing:.02em}
.rsc-hi{background:var(--coral);color:#fff}
.rsc-med{background:var(--gold);color:#fff}
.rsc-lo{background:var(--green);color:#fff}
.rsc-arch{background:var(--slate-chip);color:#fff}
.lfsav{display:inline-block;padding:2px 8px;border-radius:999px;font:700 10.5px var(--ui);letter-spacing:.02em;white-space:nowrap}
.lfsav.lfs-hi{background:#bfead6;color:#0f7a55}
.lfsav.lfs-md{background:#fde9c8;color:#8a5a00}
.lfsav.lfs-lo{background:var(--cream);color:#a9812f}
.lfsav.lfs-no{background:var(--g3);color:var(--g6)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--g4)}
.dot.on{background:var(--teal)}
.dot.warn{background:var(--gold)}
.dot.bad{background:var(--coral)}
.pend{display:inline-flex;align-items:center;gap:5px}
.pend .dot{background:var(--coral)}
.nlines{cursor:pointer;color:var(--teal-dk);font-weight:700;white-space:nowrap}
.nlines:hover{text-decoration:underline}
.t-bad{color:var(--coral-dk);font-weight:650}
.t-warn{color:#8a5a00;font-weight:650}
.t-gold{color:var(--gold);font-weight:650}
.t-ok{color:var(--g5)}
.badge{display:inline-block;font:700 9.5px var(--ui);letter-spacing:.05em;text-transform:uppercase;
  border-radius:5px;padding:2px 6px}
.badge.rc{background:var(--coral-20);color:var(--coral-dk)}
.badge.gr{background:#d8f3e8;color:var(--green)}
.loading{padding:40px;text-align:center;color:var(--g6);font:400 15px var(--ui)}
/* detail drill */
.detail td{background:var(--teal-050)!important;white-space:normal;padding:6px 16px 14px}
.dgrid h4{margin:0 0 8px;font:600 13px var(--ui);color:var(--ink);letter-spacing:.02em}
.dsecs{display:flex;flex-direction:column;gap:10px;padding:6px 0 2px;max-width:1000px}
.dsec h4{margin:0 0 5px;font:700 10.5px var(--ui);color:var(--teal-dk);letter-spacing:.07em;
  text-transform:uppercase;border-bottom:1px solid var(--teal-tint);padding-bottom:3px}
.dsec-line{margin-top:4px}
.kv{display:grid;grid-template-columns:1fr 1fr;column-gap:22px;row-gap:0}
.kv .kv-row{display:grid;grid-template-columns:minmax(120px,auto) 1fr;gap:9px;align-items:baseline;
  padding:2px 0;border-bottom:1px solid var(--teal-tint);font-size:12px;line-height:1.32}
.kv .kv-row.full{grid-column:1 / -1}
.kv .kv-row .k{color:var(--g6);font-weight:600}
.kv .kv-row .pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;background:var(--g3)}
.kv .kv-row .pill.hot{background:var(--coral-20);color:var(--coral-dk);font-weight:650}
.kv .kv-row .verbatim{display:block;margin-top:4px;font-size:11px;font-style:italic;color:var(--g6);
  border-left:2px solid var(--teal-tint);padding-left:8px;white-space:normal;line-height:1.4}
@media(max-width:720px){.kv{grid-template-columns:1fr}}
.summ{background:var(--card);border:1px solid #c7d2fe;border-left:3px solid var(--teal);
  border-radius:0 10px 10px 0;padding:11px 14px;font-size:12.5px;color:var(--ink);line-height:1.5;white-space:normal}
table.mini{font-size:11.5px;width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
table.mini th{background:var(--ink);color:#fff;text-align:left;padding:5px 9px;font:700 9px var(--ui);letter-spacing:.05em;text-transform:uppercase;position:static;white-space:nowrap}
table.mini td{padding:5px 9px;border-bottom:1px solid var(--g3);white-space:normal;vertical-align:top;background:transparent}
table.lines{font-size:12px;width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
table.lines th{background:var(--ink);color:#fff;text-align:left;padding:7px 10px;font:700 10px var(--ui);
  letter-spacing:.05em;text-transform:uppercase;cursor:pointer;white-space:nowrap;position:static}
table.lines th:hover{color:var(--teal-tint)}
table.lines th.r,table.lines td.r{text-align:right}
table.lines td{padding:6px 10px;border-bottom:1px solid var(--g3);white-space:nowrap}
table.lines tr.tot td{border-top:2px solid var(--ink);background:var(--cream);font-weight:700}
.linesx{overflow-x:auto;max-width:100%}
table.lines th.prem-fin{background:var(--teal-dk)}
table.lines td.prem-fin{background:var(--teal-050);font-weight:650}
table.lines tr.tot td.prem-fin{background:var(--cream-2)}
.chk{color:var(--green);font-weight:700}
.chk.no{color:var(--g4)}
.doss{max-width:1040px}
.doss .dhead{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 12px}
.doss .dhead .dco{font:600 15px var(--ui)}
.doss .dhead .dwho{font-size:12.5px;color:var(--g6)}
.doss .dhead .dlinks{font-size:12px;color:var(--g6)}
.doss .dhead .spacer{flex:1}
.foot{margin-top:14px;font-size:11.5px;color:var(--g6);line-height:1.7;max-width:1200px}
.pagi{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:12px 0 6px}
.pagi label{font-size:11px;color:var(--g6);font-weight:600;display:inline-flex;align-items:center;gap:6px}
.pagi select{min-width:64px;padding:5px 8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:12px var(--ui)}
.pagi input#pgJump{min-width:48px;width:48px;text-align:center;padding:5px 6px}
.pagi .pgstat{font-size:12px;color:var(--ink)}
.pagi .pgstat input{min-width:48px;width:48px}
.pagi .pgshow{font-size:11.5px;color:var(--g6);margin-left:auto}
.pagi button[disabled]{opacity:.4;cursor:default}
.empty{background:var(--card);border:1px dashed var(--line);border-radius:14px;padding:70px 30px;text-align:center}
.hidden{display:none}
/* ---- timeline (drill) ---- */
.tl{display:flex;flex-wrap:wrap;align-items:flex-start;gap:0;padding:6px 0 2px;max-width:1000px}
.tl .step{display:flex;flex-direction:column;align-items:center;min-width:96px;position:relative;flex:1}
.tl .step .bar{height:3px;background:var(--teal-tint);position:absolute;top:8px;left:50%;right:-50%;z-index:0}
.tl .step:last-child .bar{display:none}
.tl .dotm{width:17px;height:17px;border-radius:50%;border:2px solid var(--teal);background:var(--card);z-index:1}
.tl .step.done .dotm{background:var(--teal)}
.tl .step.end .dotm{width:19px;height:19px}
.tl .step.won .dotm{background:var(--teal);border-color:var(--teal-dk)}
.tl .step.lost .dotm{background:var(--card);border-color:var(--coral);border-width:3px}
.tl .step .tlab{font:600 9.5px var(--ui);letter-spacing:.03em;text-transform:uppercase;color:var(--g6);margin-top:6px;text-align:center;line-height:1.2}
.tl .step .tdt{font:600 11px var(--mono);color:var(--ink);margin-top:2px}
.tl .step.pending .tdt{color:var(--g5)}
/* ---- Customer Positioning pane ---- */
#pane-script{max-width:1080px}
.doc .eyebrow{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--coral);font-weight:700}
.doc h1{font:700 27px/1.15 var(--ui);letter-spacing:-.01em;margin:4px 0 6px}
.doc .sub{font-size:13px;color:var(--g6);margin:0 0 18px;max-width:760px;line-height:1.55}
.doc .flowbar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 14px;margin:0 0 22px;font-size:11.5px;color:var(--g6)}
.doc .flowbar .skip{text-decoration:line-through;opacity:.45}
.doc .flowbar .condf{color:var(--teal-dk);font-weight:650;border:1px dashed var(--teal);border-radius:5px;padding:1px 6px}
.doc .prep{background:var(--cream);border:1px solid #F0DFB8;border-radius:10px;padding:14px 16px;margin-bottom:22px}
.doc .prep h4{margin:0 0 8px;font:700 14px var(--ui)}
.doc .prep table{font-size:12.5px;width:auto;border-collapse:collapse}
.doc .prep td{padding:3px 14px 3px 0;border:none;white-space:normal;vertical-align:top}
.doc .prep td.k{color:var(--g6);font-weight:600}
.doc .beat{border-left:3px solid var(--line);padding:0 0 24px 20px;position:relative;margin-left:14px}
.doc .beat>.num{position:absolute;left:-15px;top:0;width:27px;height:27px;border-radius:50%;background:var(--ink);color:#fff;display:flex;align-items:center;justify-content:center;font:700 13px var(--ui)}
.doc .beat h3{font:700 17px/1.25 var(--ui);margin:2px 0 3px}
.doc .beat .meta{font-size:10.5px;color:var(--g6);text-transform:uppercase;letter-spacing:.08em;font-weight:650;margin-bottom:9px}
.doc .beat .goal{font-size:13px;color:var(--g6);margin:0 0 10px}
.doc ul.beats{margin:0 0 10px;padding-left:18px;font-size:13px}.doc ul.beats li{margin:2px 0}
.doc .say{background:var(--coral-20);border-left:3px solid var(--coral);border-radius:0 8px 8px 0;padding:11px 14px;margin:10px 0;font-size:13.5px;line-height:1.5}
.doc .say .lab{display:block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--coral-dk);margin-bottom:4px}
.doc .say em{font-style:normal;background:#fff;border:1px dashed #e6a99e;border-radius:4px;padding:0 4px;font-weight:600}
.doc .say strong.fill{background:var(--teal-tint);border:1px solid #c7d2fe;border-radius:4px;padding:0 4px;font-weight:650;color:var(--teal-dk)}
.doc .tnote{background:var(--teal-050);border-left:3px solid var(--teal);border-radius:0 8px 8px 0;padding:10px 14px;margin:10px 0;font-size:13px;color:var(--teal-dk)}
.doc .twarn{background:var(--cream);border-left:3px solid #C77700;border-radius:0 8px 8px 0;padding:10px 14px;margin:10px 0;font-size:13px;color:#6B4200}
.doc .tnote .lab,.doc .twarn .lab{font-weight:700}
.doc .cond{border:1.5px dashed var(--teal);background:var(--teal-050);border-radius:10px;padding:13px 15px;margin:15px 0}
.doc .cond .badge{display:inline-block;background:var(--teal);color:#fff;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;border-radius:5px;padding:2px 7px;margin-bottom:6px}
.doc .cond h4{margin:0 0 3px;font:700 15.5px var(--ui)}
.doc .cond .trigger{font-size:12px;color:var(--teal-dk);font-weight:640;margin:0 0 8px}
.doc .cond .say{background:#fff;border-left-color:var(--teal);color:var(--ink)}
.doc .cond .say .lab{color:var(--teal-dk)}
.doc .qgrid{display:grid;gap:8px;margin:10px 0 4px}
.doc .q{border:1px solid var(--line);border-radius:9px;padding:10px 13px;background:var(--card)}
.doc .qt{font-size:13.5px;font-weight:600}.doc .qw{font-size:12px;color:var(--g6);margin-top:4px}
.doc .tag{display:inline-block;font:700 9px var(--ui);letter-spacing:.06em;text-transform:uppercase;border-radius:5px;padding:2px 6px;margin-right:7px;vertical-align:middle}
.doc .tag.core{background:var(--teal-tint);color:var(--teal-dk)}.doc .tag.opt{background:var(--g3);color:var(--g6)}
.doc section.block{margin:26px 0 0}.doc section.block h2{font:700 18px var(--ui);margin:0 0 4px}
.doc details.obj{border:1px solid var(--line);border-radius:9px;margin-bottom:7px;background:var(--card)}
.doc details.obj summary{cursor:pointer;padding:11px 14px;font-weight:640;font-size:13.5px;list-style:none;display:flex;gap:9px;align-items:baseline}
.doc details.obj summary::-webkit-details-marker{display:none}
.doc details.obj summary::before{content:"▸";color:var(--coral);font-size:12px}
.doc details.obj[open] summary::before{content:"▾"}
.doc details.obj .body{padding:0 14px 12px 32px;font-size:13px;color:var(--g6)}
.doc .vm{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:15px 17px}
.doc .vm p{margin:0 0 9px;font-size:13.5px}
.doc .dontlist{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.doc .dontlist>div{border:1px solid var(--line);border-radius:9px;padding:12px 14px;background:var(--card)}
.doc .dontlist h5{margin:0 0 7px;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.doc .dontlist ul{margin:0;padding-left:17px;font-size:13px;color:var(--g6)}
.doc .do h5{color:var(--green)}.doc .dont h5{color:var(--coral)}
.doc .scriptbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 16px}
.doc .scriptbar .who{font-size:12.5px;color:var(--g6)}
.doc .scriptbar .scriptsearch{min-width:260px}
.doc .toggle{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--ink);cursor:pointer;user-select:none}
.doc.sampleonly .goal,.doc.sampleonly ul.beats,.doc.sampleonly .tnote,.doc.sampleonly .twarn,.doc.sampleonly .meta,.doc.sampleonly .qw,.doc.sampleonly .trigger,.doc.sampleonly .prep,.doc.sampleonly .flowbar,.doc.sampleonly .dontlist,.doc.sampleonly .qgrid .q>span.tag,.doc.sampleonly details.obj .body>*:not(.say){display:none}
.doc.sampleonly .beat{padding-bottom:12px}
/* ---- Overview tab ---- */
#pane-overview{max-width:1180px}
.ov-title{font:700 20px var(--ui);letter-spacing:-.01em;margin:2px 0 2px}
.ov-sub{font-size:12px;color:var(--g6);margin:0 0 14px}
.ov-scopebar{display:flex;align-items:center;gap:12px;margin:6px 0 14px;flex-wrap:wrap}
.ov-chips{display:inline-flex;gap:6px}
.ov-chip{font:700 12px var(--ui);padding:6px 16px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--g6);cursor:pointer}
.ov-chip:hover{background:var(--teal-050)}
.ov-chip.on{background:var(--teal);border-color:var(--teal);color:#fff}
.ov-scopesel{min-width:190px}
.ov-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 14px}
.ov-card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.ov-card-h{font:700 10px var(--ui);letter-spacing:.09em;text-transform:uppercase;color:var(--g6)}
.ov-card-n{font:600 26px/1.1 var(--ui);margin-top:8px}
.ov-card-u{font-size:12px;color:var(--g6);font-weight:400}
.ov-card-mrr{font-family:var(--mono);font-size:14px;margin-top:6px;color:var(--teal-dk)}
.ov-card-arw{color:var(--g5)}
.ov-card-risk{font-size:12px;margin-top:8px;color:var(--coral-dk);font-weight:600;display:flex;align-items:center;gap:6px}
.ov-card-risk.ov-arch{color:var(--g5);font-style:italic;font-weight:500}
.ov-hi-dot{display:inline-block;width:9px;height:9px;border-radius:2px;background:#c0392b}
.ov-legend{display:flex;gap:16px;margin:0 0 10px;font-size:11px;color:var(--g6)}
.ov-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.ov-2col{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
.ov-panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.ov-panel-h{font:700 13px var(--ui);color:var(--ink);margin-bottom:12px}
.ov-qrow{padding:8px 6px;cursor:pointer;border-radius:6px}
.ov-qrow:hover{background:var(--teal-050)}
.ov-qhead{display:flex;align-items:center;justify-content:space-between}
.ov-qlab{font:700 12px var(--ui);color:var(--ink)}
.ov-arw{color:var(--green);font-weight:700}
.ov-bar{display:flex;height:13px;margin:6px 0 4px;background:var(--g3);border-radius:3px;overflow:hidden;max-width:320px}
.ov-seg{display:block;height:13px}
.ov-seg[data-ovrisk]{cursor:pointer}
.ov-qcnt{font:400 10.5px var(--mono);color:var(--g6)}
.ov-frow{padding:7px 6px;cursor:pointer;border-radius:6px}
.ov-frow:hover{background:var(--teal-050)}
.ov-fbar-track{display:inline-block;width:190px;height:12px;background:var(--g3);border-radius:6px;overflow:hidden;vertical-align:middle;margin:5px 8px 0 0}
.ov-fbar{display:block;height:12px;background:#c0392b;border-radius:6px}
.ov-fcnt{font:700 11px var(--mono);color:var(--g6)}
.ov-rollup{padding:0;overflow:hidden}
.ov-rtable{width:100%;border-collapse:collapse;font-size:12.5px}
.ov-rscroll{max-height:452px;overflow:auto}
.ov-rtable th{text-align:left;font:700 9.5px var(--ui);letter-spacing:.06em;text-transform:uppercase;color:var(--g6);padding:12px 15px 9px;border-bottom:1px solid var(--g3)}
.ov-rtable td{padding:12px 15px;border-bottom:1px solid var(--g2)}
.ov-rtable thead th{position:sticky;top:0;z-index:2;background:var(--card)}
.ov-rtable thead th.ov-rsla-grp{background:var(--g2)}
.ov-rtable th:first-child,.ov-rtable td:first-child{position:sticky;left:0;z-index:1;background:var(--card)}
.ov-rtable thead th:first-child{z-index:3}
.ov-rrow:hover td:first-child{background:var(--teal-050)}
.ov-rrow{cursor:pointer}
.ov-rrow:hover td{background:var(--teal-050)}
.ov-rname{font-weight:600}
.ov-rnum{font-family:var(--mono);color:var(--g6)}
.ov-rhi{font-family:var(--mono);font-weight:700;color:#c0392b}
.ov-rtable td.ov-rsla5{font-family:var(--mono);font-size:12px;text-align:center;white-space:nowrap;background:var(--g2)}
.ov-rsla5 i{color:var(--g4);font-style:normal;margin:0 2px}
.ov-s5-na{color:var(--g4)}
.ov-rtable th.ov-rsla-grp{text-align:center;background:var(--g2);border-radius:8px 8px 0 0}
.ov-rsla-key{font:400 8.5px var(--mono);color:var(--g5);letter-spacing:.02em;margin-top:2px;text-transform:none}
.ov-sub{font-weight:400;color:var(--g5);font-size:9px}
.ov-rtotcell .ov-rtot{display:flex;align-items:center;gap:10px}
.ov-rtot-bar{display:inline-block;width:150px;height:12px;background:var(--g3);border-radius:6px;overflow:hidden}
.ov-rtot-bar span{display:block;height:12px;background:#c0392b;border-radius:6px}
.ov-rtot b{font-family:var(--mono);color:#c0392b}
.ov-ovlay{display:block}
.ov-rcol{display:block}
.ov-insights{padding:14px 16px}
.ov-insstrip{display:grid;grid-template-columns:repeat(5,1fr);gap:0;padding:14px 4px}
.ov-ins-col{padding:0 14px;border-right:1px solid #eef2f0}
.ov-ins-col:last-child{border-right:none}
.ov-3box{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:16px 0 20px}
.ov-3box>.ov-panel{width:100%}
.ov-ins-h{font:700 15px var(--ui);color:var(--ink);margin-bottom:6px}
.ov-ins-grp{font:700 9.5px var(--ui);letter-spacing:.05em;color:var(--g6);text-transform:uppercase;margin:12px 0 4px}
.ov-ins-row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding:2px 0}
.ov-ins-k{font-size:10.5px;color:#3a4a44}
.ov-ins-v{font:700 10.5px var(--ui);color:var(--teal-dk);white-space:nowrap}
.ov-ins-v.att{color:#c0392b;font-weight:800}
/* pct + count variant: % on the main row (right-aligned), raw opp count on its own muted sub-row beneath */
.ov-ins-rowc{padding:2px 0}
.ov-ins-rowc .ov-ins-row{padding:0}
.ov-ins-rowc .ov-ins-k{flex:1}
.ov-ins-v.num-col{min-width:44px;text-align:right;display:inline-block}
.ov-ins-cntrow{font:400 9px var(--ui);color:var(--g5);text-align:right;white-space:nowrap;line-height:1.1;margin-top:1px}
.ov-pbar{position:relative;height:11px;margin:6px 0 4px}
.ov-pbar .g{position:absolute;left:0;top:0;height:11px;background:#cdd8d3;border-radius:3px}
.ov-pbar .r{position:absolute;left:0;top:0;height:11px;background:#c0392b;border-radius:3px;cursor:pointer}
@media(max-width:1000px){.ov-3box{grid-template-columns:1fr}.ov-insstrip{grid-template-columns:repeat(2,1fr)}.ov-ins-col{border-right:none}}
@media(max-width:820px){.ov-cards{grid-template-columns:1fr}.ov-2col{grid-template-columns:1fr}.ov-ovlay{grid-template-columns:1fr}.ov-insstrip{grid-template-columns:1fr}}
/* filterable stage tiles + risk H/M/L boxes */
.ov-card-click{cursor:pointer;transition:border-color .12s ease,box-shadow .12s ease}
.ov-card-click:hover{border-color:var(--teal)}
.ov-card-on{border-color:var(--teal);box-shadow:0 0 0 2px var(--teal-tint)}
.ov-risktier{display:block}
.ov-risktier.on{background:var(--teal-050)}
.ov-riskdot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.ov-riskdetail{margin-top:10px;border-top:1px solid var(--line);padding-top:9px}
.ov-riskdetail-h{font:700 10px var(--ui);letter-spacing:.05em;text-transform:uppercase;color:var(--g6);margin-bottom:6px}
/* Guide pane */
#pane-guide{max-width:860px}
.guidedoc{max-width:820px;line-height:1.62;color:var(--ink);font-size:14px}
.guidedoc h1{font:700 26px/1.2 var(--ui);letter-spacing:-.01em;margin:6px 0 10px}
.guidedoc h2{font:700 19px var(--ui);margin:26px 0 6px;border-bottom:1px solid var(--line);padding-bottom:4px}
.guidedoc h3{font:700 15px var(--ui);margin:18px 0 4px;color:var(--teal-dk)}
.guidedoc p{margin:8px 0}
.guidedoc ul{margin:6px 0 12px;padding-left:22px}
.guidedoc li{margin:3px 0}
.guidedoc hr{border:none;border-top:1px solid var(--line);margin:20px 0}
.guidedoc code{font-family:var(--mono);font-size:12px;background:var(--g3);padding:1px 5px;border-radius:4px}
.guidedoc strong{font-weight:700}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div>
      <div class="brand">Benefits Advising <b>Hub</b><span class="verbadge">alpha</span></div>
      <div class="sub">Renewal Workbench &amp; Customer Outreach Platform &middot; all 2026 cohorts (7/1&ndash;12/1)</div>
    </div>
    <div class="spacer"></div>
    <div class="chip cohort" id="cohortPill">All cohorts</div>
  </div>

  <div class="tabs">
    <button class="tab on" data-pane="overview">Overview</button>
    <button class="tab" data-pane="open">Open <span class="cnt" id="cnt-open"></span></button>
    <button class="tab" data-pane="pf">Pending Fulfillment <span class="cnt" id="cnt-pf"></span></button>
    <button class="tab" data-pane="closed">Closed <span class="cnt" id="cnt-closed"></span></button>
    <button class="tab" data-pane="script">Customer Positioning</button>
    <button class="tab" data-pane="guide">Read Me</button>
  </div>

  <div class="pane" id="pane-overview">
    <div id="ovScope"></div>
    <div id="ovBody"></div>
  </div>

  <div class="pane on" id="pane-table">
    <div class="kpis" id="kpis"></div>
    <div class="bar">
      <div class="fld"><label>Search</label><input type="text" id="fSearch" placeholder="Company, advisor, or PE..."></div>
      <div id="mdAdv"></div>
      <div id="mdPE"></div>
      <div id="mdStage"></div>
      <div id="mdTier"></div>
      <div id="mdCohort"></div>
      <div class="fld"><label>Risk</label><div id="mdRisk"></div></div>
      <div class="spacer"></div>
    </div>
    <div class="tbltop" id="tblTop"><div class="tbltop-inner" id="tblTopInner"></div></div>
    <div class="tblwrap" id="tblwrap">
      <table id="tbl">
        <thead><tr class="grp" id="grpRow"></tr><tr class="cols" id="hdr"></tr></thead>
        <tbody id="body"></tbody>
      </table>
    </div>
    <div class="foot" id="foot"></div>
  </div>

  <div class="pane" id="pane-script">
    <div class="scriptbar">
      <button class="btn ghost sm" id="bBackTable">&larr; Back to opps</button>
      <button class="btn ghost sm hidden" id="bGeneric">Generic positioning</button>
      <input type="text" id="scriptSearch" class="scriptsearch" list="scriptCompanies" placeholder="Look up a customer&hellip;" autocomplete="off">
      <datalist id="scriptCompanies"></datalist>
      <span class="who" id="scriptWho"></span>
      <div class="spacer" style="flex:1"></div>
      <label class="toggle"><input type="checkbox" id="tSample"> Sample lines only</label>
    </div>
    <div class="doc" id="scriptDoc"></div>
  </div>

  <div class="pane" id="pane-guide">
    <div class="guidedoc">__GUIDEHTML__</div>
  </div>
</div>

<script id="hubdata" type="application/json">__HUBDATA__</script>
<script>
/* ============================================================ data + state */
const HUB = JSON.parse(document.getElementById("hubdata").textContent);
const TODAY = new Date(new Date().toISOString().slice(0,10)+"T00:00:00");
const TAB_CLOSED = new Set(["Closed Won","Closed Lost","Order Lost","Closed Admin"]);
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const LS_KEY = "advhub_state_v1";
let PAGE = 1;                // 1-based page over the filtered+sorted set
let PAGE_SIZE = 100;         // 50 | 100 | 250
let TAB = "open";            // "open" | "pf" | "closed"
let CLOSED = false;          // derived: TAB==="closed"
let SORT = {k:"tier", dir:1};
let OPEN = null;             // drill row opp id
let LINES_OPEN = false;
let DRILL_SORT = {k:"enr_before", dir:-1};

const tabOf = r => { const s=r.stage||""; return TAB_CLOSED.has(s) ? "closed" : (s==="Pending Fulfillment" ? "pf" : "open"); };

function cohortLabel(c){
  const m = /^(\d{4})-(\d{2})/.exec(c||""); if(!m) return c||"—";
  return `${MONTHS[(+m[2])-1]} ${m[1]} (${+m[2]}/1)`;
}
HUB.forEach(r => {
  if (typeof r.advisor === "string") r.advisor = r.advisor.replace(/\*+\s*$/,"").trim();
  if (typeof r.pe      === "string") r.pe      = r.pe.replace(/\*+\s*$/,"").trim();
  if (!("cohort" in r)){ const rd = String(r.renewal_date||"");
    r.cohort = /^\d{4}-\d{2}/.test(rd) ? rd.slice(0,7) : ""; }
  // Outreach tier: computed for all tabs (last value shown greyed/archived on PF & Closed).
  {
    const flags = [];
    // P1: default automation — default automation completed (Y)
    if (r.default_automation==="Y") flags.push(1);
    // P2: level-funded quote with a real savings band (fires on High/Medium/Low, not No)
    if (r.lf_quote && r.lf_savings_band && r.lf_savings_band!=="No") flags.push(2);
    // P3: medical projected Δ >= 15 and computed (not an estimate)
    if (r.rate_increase_pct != null && r.rate_increase_pct >= 15 && r.rate_status && !/^estimate/i.test(r.rate_status)) flags.push(3);
    // P4: data gap
    if (!r.enrollees || !r.mrr) flags.push(4);
    // P5: selection deadline present
    if (r.selection_deadline) flags.push(5);
    r.queue_tier = flags.length ? Math.min(...flags) : 5;
    // annotation labels — descriptive only, do NOT change the numeric tier
    const annos = [];
    if (r.sep==="Y") annos.push("SEP");
    if (r.recert_ticket==="Y" || /recert/i.test(r.recert_status||"")) annos.push("Recertification");
    if (/packet/i.test(r.blocked_reason||"")) annos.push("Renewal packet needed");
    if (/^estimate/i.test(r.rate_status||"")) annos.push("Estimated increase");
    r.tier_annos = annos;
  }
});

/* ============================================================ utils */
const el = id => document.getElementById(id);
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const D = s => s ? new Date(String(s).slice(0,10)+"T00:00:00") : null;
const dayDiff = (a,b) => Math.round((a-b)/86400000);
const dUntil = s => s ? dayDiff(D(s),TODAY) : null;
const money = v => v==null ? "" : "$"+Math.round(v).toLocaleString();
const money1 = v => v==null ? "" : "$"+(Math.round(v*100)/100).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const fund = v => ({fully_insured:"Fully insured",level_funded:"Level funded",self_funded:"Self funded"})[v] || (v||"");
const fundShort = v => ({fully_insured:"FI",level_funded:"LF",self_funded:"SF"})[v] || (v?String(v).replace(/[^A-Za-z]/g,"").slice(0,2).toUpperCase():"—");
// transition chip: "FI→LF" — only render the transition when CLOSED (funding_after is
// menu-ambiguous pre-close, so pre-close we show just the current funding).
const fundTransChip = (cur, after) => {
  const c = fundShort(cur);
  if (!CLOSED || after==null || after==="") return c;
  return `${c}→${fundShort(after)}`;
};
const DASH = `<span class="t-ok">—</span>`;
const or = v => (v==null || v==="") ? DASH : v;                 // drill value fallback
const primaryLine = r => { const ls=r.lines||[]; if(!ls.length) return null;
  return ls.slice().sort((a,b)=>(b.enr_before||0)-(a.enr_before||0))[0]; };
const isY = v => v==="Y";
// short M/D from a YYYY-MM-DD date, and the call-disposition tag (VM kept upper, others lowercased)
const mdShort = dt => dt ? ((+String(dt).slice(5,7))+"/"+(+String(dt).slice(8,10))) : "";
const callDispTag = d => d==null ? "" : (d==="VM" ? "VM" : String(d).toLowerCase());
const hasRecert = r => isY(r.recert_ticket) || /recert/i.test(r.recert_status||"");
const rows = () => HUB.filter(r => tabOf(r)===TAB);

/* ============================================================ columns */
const medLine = r => (r.lines||[]).find(l => l.benefit_type==="medical") || null;
const lineEnr = (r,bt) => { const l=(r.lines||[]).find(x=>x.benefit_type===bt); return l?l.enr_before:null; };
const lineEnrA = (r,bt) => { const l=(r.lines||[]).find(x=>x.benefit_type===bt); return l?l.enr_after:null; };
const BT_DEFS = [["medical","Medical"],["dental","Dental"],["vision","Vision"],
                 ["life","Life"],["short_term_disability","STD"],["long_term_disability","LTD"]];
const BT_PRESENT = BT_DEFS.filter(([bt]) => HUB.some(r => (r.lines||[]).some(l => l.benefit_type===bt)));
const PIN_W = {company:210, advisor:132, pe:120};

// tabs: "o"=Open "p"=Pending Fulfillment "c"=Closed. omitted => all three.
const nn = v => (v==null? -1 : v);
const BASE_COLS = [
  // Frozen
  {k:"company",g:"customer",t:"Customer",pin:1,s:r=>r.company||""},
  {k:"advisor",g:"customer",t:"Advisor",pin:1,s:r=>r.advisor||""},
  {k:"pe",     g:"customer",t:"PE",     pin:1,s:r=>r.pe||""},
  // Outreach priority
  {k:"tier",   g:"queue", t:"Outreach priority", s:r=>r.queue_tier},
  {k:"risk",   g:"queue", t:"Risk", s:r=>riskCached(r).score},
  // Closed-only
  {k:"outcome",g:"closed",t:"Outcome",tabs:"c",s:r=>r.outcome||""},
  {k:"closedon",g:"closed",t:"Closed on",tabs:"c",s:r=>r.closed_on||""},
  {k:"mrrb",   g:"closed",t:"MRR before",tabs:"c",s:r=>nn(r.mrr_before)},
  {k:"mrra",   g:"closed",t:"MRR after", tabs:"c",s:r=>nn(r.mrr_after)},
  // General
  {k:"renewal",g:"general",t:"Renewal date", s:r=>r.renewal_date||""},
  {k:"survey", g:"general",t:"Survey answered",s:r=>isY(r.survey_answered)?1:0},
  {k:"seldl",  g:"general",t:"Selection deadline",s:r=>r.selection_deadline||"9999"},
  {k:"subdl",  g:"general",t:"Submission deadline",s:r=>r.submission_deadline||"9999"},
  {k:"d2r",    g:"general",t:"Days to Renewal",s:r=>r.days_to_renewal??9999},
  {k:"d2s",    g:"general",t:"Days to Submission",s:r=>{const d=dUntil(r.submission_deadline);return d==null?99999:d;}},
  {k:"lead",   g:"general",t:"Lead days",s:r=>r.lead_days??99999},
  {k:"stage",  g:"general",t:"Stage",   s:r=>r.stage||""},
  {k:"dis",    g:"general",t:"Days in Stage",s:r=>r.days_in_stage??-1},
  {k:"mrr",    g:"general",t:"MRR",   tabs:"op", s:r=>r.mrr??-1},
  {k:"funding",g:"general",t:"Funding", s:r=>fund(r.funding)},
  {k:"enr",    g:"general",t:"ENR (med)",s:r=>r.enrollees??-1},
  {k:"carrier",g:"general",t:"Carrier (med)",s:r=>(medLine(r)||{}).carrier||""},
  {k:"packets",g:"general",t:"Packets", s:r=>r.packets_files??-1},
  {k:"rate",   g:"general",
     t:()=>tabCode()==="c"?"Premium Δ (Final)":"Premium Δ (Projected)",
     s:r=>{ if(tabCode()==="c"){ const ml=medLine(r); const v=ml?ml.d_fin:null; return v==null?-999:v; } return r.rate_increase_pct??-999; },
     ttl:()=>({o:"Medical projected renewal Δ vs successor (EYO)",p:"Medical projected renewal Δ vs successor (EYO)",c:"Medical final selected Δ (enrolled)"}[tabCode()])},
  {k:"nlines", g:"line",   t:"Lines ▸",s:r=>r.num_lines??-1},
  // Flags
  {k:"lf",     g:"flags", t:"LF",       s:r=>r.lf_quote||""},
  {k:"lfsav",  g:"flags", t:"LF savings",s:r=>{const b=r.lf_savings_band;return b==="High"?4:b==="Medium"?3:b==="Low"?2:b==="No"?1:-1;}},
  {k:"recert", g:"flags", t:"Recert",   s:r=>hasRecert(r)?1:0},
  {k:"sep",    g:"flags", t:"SEP",      s:r=>isY(r.sep)?1:0},
  {k:"bor",    g:"flags", t:"BoR/Term", s:r=>isY(r.bor_term)?1:0},
  {k:"autoren",g:"flags", t:"Auto-renewal",s:r=>isY(r.auto_renewal)?1:0},
  {k:"defauto",g:"flags", t:"Default automation",s:r=>isY(r.default_automation)?1:0},
  {k:"intro",  g:"contact", t:"Intro (done)", s:r=>isY(r.intro_call)?1:0},
  {k:"introc", g:"contact", t:"Intro Connect",s:r=>isY(r.intro_connect)?1:0},
  {k:"emaildue",g:"contact",t:"Email due",tabs:"op",s:r=>isY(r.email_due)?(r.email_due_hoop_hrs??1):-1},
  {k:"emailrecv",g:"contact",t:"Received",tabs:"op",s:r=>r.email_received_date||""},
  {k:"lastout",g:"contact",t:"Last email out",s:r=>r.last_outbound_email_date||""},
  {k:"lastin", g:"contact",t:"Last email in", s:r=>r.last_inbound_email_date||""},
  {k:"lastupd",g:"contact", t:"Last call",s:r=>r.last_call_date||""},
  // Sentiment (own group, right after Flags). Per-tab: Open=all-survey count · PF=in-app · Closed=CSAT + in-app
  {k:"survcount",g:"sentiment",t:"Surveys (12mo)",tabs:"o",s:r=>r.all_survey_count??-1},
  {k:"inapp",  g:"sentiment", t:"In-app",tabs:"pc",s:r=>r.inapp_current??-1},
  {k:"csat",   g:"sentiment", t:"CSAT",    tabs:"c", s:r=>r.csat_current??-1},
  // Recommendation
  {k:"recsent", g:"rec",  t:"Default rec sent", s:r=>r.default_rec_sent||""},
  {k:"d2def",   g:"rec",  t:"Time to rec sent",s:r=>r.days_to_rec_cycle??99999,
     ttl:()=>"Opp create → first recommendation sent (days)"},
  {k:"trfd",    g:"rec",  t:"Time in RFD",s:r=>r.days_to_default??99999,
     ttl:()=>"Time in RFD (SLO) — days in Ready-for-Default-Package"},
  {k:"altreq",  g:"rec",  t:"Alt requested",s:r=>(isY(r.alt_requested)||r.alt_requested_date)?1:0},
  {k:"altcreated",g:"rec",t:"Alt created", s:r=>r.alt_created??-1},
  {k:"altpub",  g:"rec",  t:"Alt published",s:r=>r.alt_published_date||""},
  {k:"days2alt",g:"rec",  t:"Days to alt",  s:r=>r.days_to_alt??99999},
  {k:"terc",   g:"rec",  t:"Time in ERC",s:r=>r.time_in_erc??99999,
     ttl:()=>"Time in ER Confirm — days in stage"},
  // Benefit order  (BO status MUST remain the last column on PF/Closed)
  {k:"tix",    g:"bo",    t:"Tickets → Advising",tabs:"pc",s:r=>r.tickets_to_advising??-1},
  {k:"opentix",g:"bo",    t:"Open tickets",tabs:"pc",s:r=>r.open_tickets??-1},
  {k:"opentixsla",g:"bo", t:"Open >5d",tabs:"pc",s:r=>r.open_tickets_past_sla??-1},
  {k:"bostatus",g:"bo",   t:"BO status",tabs:"pc",s:r=>r.bo_status||""}   // MUST be last on PF/Closed
];
const LINE_COLS = BT_PRESENT.map(([bt,lab]) => ({
  k:"ln_"+bt, g:"line", t:lab, line:true, bt:bt,
  s:r=>{ const v=lineEnr(r,bt); return v==null?-1:v; }
}));
const COLS = (()=>{ const i=BASE_COLS.findIndex(c=>c.k==="nlines");
  return BASE_COLS.slice(0,i+1).concat(LINE_COLS, BASE_COLS.slice(i+1)); })();
const GROUP_LABEL = {customer:"Customer", queue:"Outreach priority", closed:"Closed-only", general:"General", line:"Line (current)", flags:"Flags", contact:"Customer Contact", sentiment:"Sentiment", rec:"Recommendation", bo:"Benefit order"};
const GROUP_ORDER = [...new Set(COLS.map(c=>c.g))];
const tabCode = () => TAB==="open"?"o":TAB==="pf"?"p":"c";
const colInTab = c => !c.tabs || c.tabs.includes(tabCode());
const visibleCols = () => COLS.filter(c => (c.line ? LINES_OPEN : true) && colInTab(c));
function pinLeft(cols, i){ let x=0; for(let j=0;j<i;j++){ if(cols[j].pin) x+=PIN_W[cols[j].k]||120; } return x; }

/* ============================================================ tier + helpers */
function tierChip(r, showAnno){
  if (r.queue_tier==null) return DASH;
  const t = r.queue_tier;
  const reason = TIER_NAMES[t]||"";
  const annos = r.tier_annos||[];
  const annoTip = annos.length ? ` · ${annos.join(", ")}` : "";
  let out = `<span class="tier t${t}" title="Outreach priority P${t} — ${esc(reason)}${esc(annoTip)}">P${t}</span>`
       + (reason ? ` <span class="t-ok" style="font-size:10.5px">${esc(reason)}</span>` : "");
  if (showAnno && annos.length) out += " " + annos.map(a=>`<span class="badge rc">${esc(a)}</span>`).join(" ");
  return out;
}
function dot(state, title){
  const cls = state==="bad"?"bad":state==="warn"?"warn":state==="on"?"on":"";
  return `<span class="dot ${cls}" title="${esc(title)}"></span>`;
}
function rateCell(r){
  // medical-anchored premium Δ. Open/PF -> rate_increase_pct (Projected);
  // Closed -> medical line d_fin (Final). Null Closed d_fin -> em-dash.
  if (tabCode()==="c"){
    const ml = medLine(r); const v = ml ? ml.d_fin : null;
    if (v==null) return DASH;
    const cls = v>=30?"t-bad":v>=20?"t-warn":v>=15?"t-gold":"";
    return `<span class="num ${cls}" title="Final selected medical premium Δ (enrolled)">${(v>0?"+":"")+v.toFixed(1)}%</span>`;
  }
  const v = r.rate_increase_pct, st = r.rate_status||"";
  if (v==null) return `<span class="t-ok" title="${esc(st)}">${esc(st.replace(/^estimate /,"est ")||"—")}</span>`;
  const cls = v>=30?"t-bad":v>=20?"t-warn":v>=15?"t-gold":"";
  const suffix = (st && st!=="computed") ? ` <span class="t-ok" style="font-size:10px">${esc(st.replace(/^estimate /,"est "))}</span>` : "";
  return `<span class="num ${cls}" title="Projected medical renewal Δ vs successor · ${esc(st)}">${v.toFixed(1)}%</span>${suffix}`;
}
const ICONS = {
  hippo: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 13a6 4.5 0 0 1 6-4.5h4a5.5 4 0 0 1 4.4 2.2l1.6.4v3l-1.4.3A5.5 4 0 0 1 17 17v2h-2.5v-1.4h-3V19H9v-2.2A6 4.5 0 0 1 4 13z"/><path d="M9.5 8.6A2.4 2 0 0 1 13 7.4"/><circle cx="15.4" cy="12.4" r=".5"/></svg>`,
  sf:    `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 18H7.5a3.5 3.5 0 0 1-.6-6.95A4.5 4.5 0 0 1 15.6 9.6 3.2 3.2 0 0 1 17 18z"/></svg>`,
  bo:    `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="3" rx="1"/><path d="M8.5 11h7M8.5 14h7M8.5 17h4"/></svg>`
};
function coIcon(url, kind, title){
  const svg = ICONS[kind] || "";
  return url
    ? `<a class="ic" href="${esc(url)}" target="_blank" rel="noopener" title="${esc(title)}">${svg}</a>`
    : `<span class="ic off" title="${esc(title)} — none on record">${svg}</span>`;
}

/* ============================================================ risk engine
   Per-tab risk profile computed client-side from existing row fields.
   Open  -> riskOpen  (EYO 2 pre-selection model, tickets intentionally removed)
   PF    -> riskPF    (4-factor fulfillment model)
   Closed-> riskPF but marked archived. tier: >=35 High · >=18 Med · else Low. */
const EARLY = new Set(["Open","SAL","Attempting Contact","New","Working","Nurturing"]);
const MID   = new Set(["Engaged","ER Confirm"]);
function _daysSince(s){ const d=dUntil(s); return d==null?null:-d; }   // days since a past date
function riskOpen(r){
  const bl = (r.blocked_reason||"");
  const sigs = [];
  // unworked (15)
  const early = EARLY.has(r.stage)?1: MID.has(r.stage)?0.5:0;
  const dtr = r.days_to_renewal;
  const unwSev = early * (dtr==null?0.2 : dtr<=30?1 : dtr<=45?0.8 : dtr<=60?0.5 : 0.2);
  sigs.push({key:"unworked", w:15, sev:unwSev, reason:`unworked close to renewal — still in ${r.stage}, ${r.days_to_renewal<0?Math.abs(r.days_to_renewal)+" days past renewal":r.days_to_renewal+" days to renewal"}`});
  // termbor (15)
  const tbSev = /Pending Termination|BoR Away/i.test(bl)?1 : /BoR Incomplete/i.test(bl)?0.7 : 0;
  sigs.push({key:"termbor", w:15, sev:tbSev, reason:`blocked: term/BOR away — ${bl}`});
  // silence — gone-quiet #1: no outbound email in 21+ days (null = fire). Weight 0: drives the tier via the gone-quiet floor override, not the weighted score.
  const so = _daysSince(r.last_outbound_email_date);
  const siFire = (so==null) || (so>21);
  sigs.push({key:"silence", w:0, sev:siFire?1:0, reason:(so==null?`No recent email outreach — no outbound email logged`:`No recent email outreach — ${so} days since we emailed`)});
  // rate (12)
  const inc = r.rate_increase_pct;
  const rtSev = inc==null?0 : inc>=30?1 : inc>=20?0.6 : inc>=15?0.3 : 0;
  sigs.push({key:"rate", w:12, sev:rtSev, reason:`rate increase ${r.rate_increase_pct}%`});
  // noresp — gone-quiet #2: no inbound customer reply in 21+ days (null = fire). Weight 0 (see silence).
  const si = _daysSince(r.last_inbound_email_date);
  const nrFire = (si==null) || (si>21);
  sigs.push({key:"noresp", w:0, sev:nrFire?1:0, reason:(si==null?`No recent customer response — no reply logged`:`No recent customer response — ${si} days since they replied`)});
  // callconnect — gone-quiet #3: no live call connect in 21+ days (null = fire). Weight 0 (see silence).
  const sc=_daysSince(r.last_connect_date);
  const ccFire = (sc==null) || (sc>21);
  sigs.push({key:"callconnect", w:0, sev:ccFire?1:0, reason:(sc==null?`No recent call connects — no live connect logged`:`No recent call connects — ${sc} days since a live connect`)});
  // lategen (10)  — negative lead_days counts as <60 -> 1
  const ld = r.lead_days;
  const lgSev = ld==null?0 : ld<60?1 : ld<75?0.5 : 0;
  sigs.push({key:"lategen", w:10, sev:lgSev, reason:`late-generated opp (${r.lead_days}d lead)`});
  // stagnant (10)
  const dis = r.days_in_stage;
  const stSev = dis==null?0 : dis>21?1 : dis>14?0.66 : dis>7?0.33 : 0;
  sigs.push({key:"stagnant", w:10, sev:stSev, reason:`days in SFDC stage — ${r.days_in_stage} days in ${r.stage}`});
  // nointro (10)
  sigs.push({key:"nointro", w:10, sev:isY(r.intro_call)?0:1, reason:`intro call not complete`});
  // (label parity: OV_OPEN_FACTOR_LABEL uses EYO 2 phrasing)
  // deadline (10) — selection deadline
  const dd = dUntil(r.selection_deadline);
  const dlSev = dd==null?0 : dd<0?1 : dd<=7?0.6 : dd<=14?0.3 : 0;
  sigs.push({key:"deadline", w:10, sev:dlSev, reason:(dd<0?`selection deadline passed ${-dd}d ago`:`selection deadline in ${dd}d`)});   // EYO 2: "Selection deadline"
  // subdl (10) — submission deadline, same mapping
  const sd = dUntil(r.submission_deadline);
  const sdSev = sd==null?0 : sd<0?1 : sd<=7?0.6 : sd<=14?0.3 : 0;
  sigs.push({key:"subdl", w:10, sev:sdSev, reason:(sd<0?`submission deadline passed ${-sd}d ago`:`submission deadline in ${sd}d`)});   // EYO 2: "Submission deadline"
  // packet (8)
  const pkSev = /Packet Needed/i.test(bl)?1 : ((r.packets_files==0||r.packets_files==null)&&r.packet_carriers)?0.4 : 0;
  sigs.push({key:"packet", w:8, sev:pkSev, reason:`renewal packet missing`});   // EYO 2: "Renewal packet missing"
  // altsla (8)
  let asSev = 0;
  if (r.alt_requested_date){
    let gap = r.alt_published_date ? (r.days_to_alt) : _daysSince(r.alt_requested_date);
    gap = gap==null?0:gap;
    asSev = gap>3?1 : gap==3?0.5 : 0;
  }
  sigs.push({key:"altsla", w:8, sev:asSev, reason:`alternates requested > 3d`});
  // recert (8)
  const rl = r.recert_lateness_days;
  const rcSev = (rl>0)? (rl>60?1:rl>30?0.7:rl>14?0.4:0.25) : ((r.recert_ticket||r.recert_status||/recert/i.test(bl))?0.5:0);
  sigs.push({key:"recert", w:8, sev:rcSev, reason:(rl>0?`recertification ${rl} days late`:`recertification flagged`)});
  // lfpend (6) — LF savings available but not yet recommended in an alt package (LF-dash definition)
  { const band=r.lf_savings_band; const posit=(band==="High"||band==="Medium"||band==="Low");
    const inAlt=(r.lf_in_alt==="Y");
    const sev = (posit && !inAlt) ? (band==="High"?1:band==="Medium"?0.7:0.4) : 0;
    sigs.push({key:"lfpend", w:6, sev:sev, reason:`level-funded quote pending — LF savings (${band}) not yet recommended in an alt`}); }
  // sepgr (6)
  sigs.push({key:"sepgr", w:6, sev:isY(r.sep)?1:0, reason:`SEP / GR flagged`});   // EYO 2: "SEP / GR"
  const WTOTAL_OPEN = 128;   // 158 - 30: silence/noresp/callconnect now weight 0; the 3 "gone quiet" signals drive the tier via the floor override in riskOf(), not the weighted score.
  let acc=0; sigs.forEach(s=>{ acc += s.w*s.sev; });
  const score = Math.round(100*acc/WTOTAL_OPEN);
  // gone-quiet count (0-3): how many of the 3 recency signals fired (>21d or null). Used by riskOf() to floor the tier: 3 -> High, 1-2 -> Med, 0 -> no floor.
  const goneQuiet = ["silence","noresp","callconnect"].reduce((n,k)=>{ const s=sigs.find(x=>x.key===k); return n + (s && s.sev>0 ? 1 : 0); },0);
  const firing = sigs.filter(s=>s.sev>0).sort((a,b)=>(b.w*b.sev)-(a.w*a.sev));
  const reasons = firing.map(s=>s.reason);
  return {score, reasons, firing, goneQuiet};
}
function riskPF(r){
  const sigs = [];
  // sentiment (30)
  const cur = (r.in_app_date && r.cycle_open && r.in_app_date >= r.cycle_open);
  const ia = parseFloat(r.inapp_current);
  const cmt = !!r.in_app_comment;
  const seSev = (cur && (!isNaN(ia)||cmt)) ? (ia<=2?1 : ia<=3?0.7 : (cmt?0.7:0)) : 0;
  sigs.push({key:"sentiment", w:30, sev:seSev, reason:`in-app sentiment ${r.inapp_current} this cycle`});
  // ticket (30)
  const tk = r.tickets_to_advising||0;
  const tkSev = tk>=3?1 : tk==2?0.7 : tk==1?0.4 : 0;
  sigs.push({key:"ticket", w:30, sev:tkSev, reason:`${r.tickets_to_advising} open OA→advising ticket${r.tickets_to_advising==1?"":"s"}`});
  // recert (20)
  const rcSev = (r.recert_status && r.recert_status!=="Recert Approved")?1:0;
  sigs.push({key:"recert", w:20, sev:rcSev, reason:`recert still open (${r.recert_status})`});
  // within1wk (30)
  const dd = dUntil(r.submission_deadline);
  const w1Sev = (dd!=null&&dd>=0&&dd<=7)?1 : (dd!=null&&dd>=8&&dd<=14)?0.5 : 0;
  sigs.push({key:"within1wk", w:30, sev:w1Sev, reason:`fulfillment in ${dUntil(r.submission_deadline)} day${dUntil(r.submission_deadline)==1?"":"s"}`});
  // autoren (20) — auto-renewing into a rate increase
  const inc = r.rate_increase_pct;
  const arSev = isY(r.auto_renewal) ? (inc>=20?1 : inc>=14?0.6 : 0.3) : 0;
  sigs.push({key:"autoren", w:20, sev:arSev, reason:(inc!=null ? `auto-renewing into a ${inc}% increase` : "auto-renewal")});
  const WTOTAL_PF = 130;
  let acc=0; sigs.forEach(s=>{ acc += s.w*s.sev; });
  const score = Math.round(100*acc/WTOTAL_PF);
  const firing = sigs.filter(s=>s.sev>0).sort((a,b)=>(b.w*b.sev)-(a.w*a.sev));
  const reasons = firing.map(s=>s.reason);
  return {score, reasons, firing};
}
function riskOf(r){
  const t = tabOf(r); let base, archived=false;
  if (t==="open") base = riskOpen(r);
  else if (t==="pf") base = riskPF(r);
  else { base = riskPF(r); archived = true; }
  const score = base.score;
  let tier = score>=35?"High" : score>=18?"Med" : "Low";
  // Gone-quiet floor override (Open only): 3 of 3 recency signals -> at least High; 1-2 -> at least Med; 0 -> no floor.
  // Acts as a floor (max) so substantive weighted risk can still raise the tier but gone-quiet can't lower it.
  if (t==="open" && base.goneQuiet!=null){
    const floor = base.goneQuiet>=3?"High" : base.goneQuiet>=1?"Med" : "Low";
    const RANK = {Low:0, Med:1, High:2};
    if (RANK[floor] > RANK[tier]) tier = floor;
  }
  return {score, tier, reasons:base.reasons, firing:base.firing||[], archived, goneQuiet:base.goneQuiet};
}
// memoize per row (tabOf + TODAY are stable for the page life) to avoid recompute
function riskCached(r){ if(!r.__risk) r.__risk = riskOf(r); return r.__risk; }

/* ============================================================ cell render */
function cell(r,k){
  if (k.indexOf("ln_")===0){ const bt=k.slice(3), v=lineEnr(r,bt);
    if (CLOSED){ const a=lineEnrA(r,bt);
      if (v==null && a==null) return DASH;
      return `<span class="num">${v==null?"—":v}→${a==null?"—":a}</span>`; }
    return v==null ? DASH : `<span class="num">${v}</span>`; }
  switch(k){
    case "tier":    return (TAB==="open") ? tierChip(r) : `<span class="chip arch" title="archived — last outreach priority${r.queue_tier!=null?" · P"+r.queue_tier:""}">${r.queue_tier!=null?esc(TIER_NAMES[r.queue_tier]||("P"+r.queue_tier)):"—"}</span>`;
    case "advisor": return esc(r.advisor||"—");
    case "pe":      return esc(r.pe||"—");
    case "risk":    { const x=riskCached(r);
                      const cls=x.archived?"rsc-arch":(x.tier==="High"?"rsc-hi":x.tier==="Med"?"rsc-med":"rsc-lo");
                      const chip=`<span class="rsc ${cls}" title="${x.archived?"archived — last risk":"risk"}">${x.score} ${x.tier}</span>`;
                      const rs=x.reasons.slice(0,3);
                      const tail=rs.length?` <span class="t-ok" style="font-size:10.5px">· ${rs.map(esc).join(" · ")}</span>`:"";
                      return chip+tail; }
    case "company": {
      const cn = r.sf_opp_url ? `<a class="cn" href="${esc(r.sf_opp_url)}" target="_blank" rel="noopener">${esc(r.company)}</a>` : `<span class="cn">${esc(r.company)}</span>`;
      const icons = coIcon(r.hippo_url,"hippo","Hippo") + coIcon(r.sf_opp_url,"sf","Salesforce opp") + coIcon(r.bo_url,"bo","Benefit order");
      return `<div class="co"><span class="expand" title="Expand row">▸</span>${cn}<span class="icons">${icons}</span></div>`;
    }
    case "outcome": return r.outcome ? `<span class="chip ${r.outcome==="Won"?"won":"lost"}">${esc(r.outcome)}</span>` : DASH;
    case "closedon":return r.closed_on ? `<span class="num">${esc(r.closed_on)}</span>` : DASH;
    case "renewal": return `<span class="num">${esc(r.renewal_date||"—")}</span>`;
    case "survey":  return isY(r.survey_answered) ? `<span class="badge gr">Y</span>` : `<span class="t-ok">N</span>`;
    case "seldl":{ const sd=dUntil(r.selection_deadline); const cls=sd==null?"":sd<0?"t-bad":sd<=7?"t-warn":"";
      return r.selection_deadline?`<span class="num ${cls}">${esc(r.selection_deadline)}</span>`:DASH; }
    case "subdl":{ const sd=dUntil(r.submission_deadline); const cls=sd==null?"":sd<0?"t-bad":sd<=7?"t-warn":"";
      return r.submission_deadline?`<span class="num ${cls}">${esc(r.submission_deadline)}</span>`:DASH; }
    case "d2r":{ const d=r.days_to_renewal; return d==null?DASH:`<span class="num ${d<=30?"t-bad":d<=45?"t-warn":""}">${d}</span>`; }
    case "d2s":{ const d=dUntil(r.submission_deadline); return d==null?DASH:`<span class="num ${d<0?"t-bad":d<=7?"t-warn":""}">${d}</span>`; }
    case "lead":{ const d=r.lead_days; return d==null?DASH:`<span class="num ${d<=75?"t-warn":""}${d<0?" t-bad":""}" title="opp created → renewal (lead time)">${d}</span>`; }
    case "stage":   return `<span class="chip stage">${esc(r.stage||"—")}</span>`;
    case "dis":{ const d=r.days_in_stage; return d==null?DASH:`<span class="num ${d>21?"t-bad":d>14?"t-warn":""}">${d}${r.days_in_stage_approx?"*":""}</span>`; }
    case "mrr":     return r.mrr!=null?`<span class="num">${money(r.mrr)}</span>`:DASH;
    case "mrrb":    return r.mrr_before!=null?`<span class="num">${money(r.mrr_before)}</span>`:DASH;
    case "mrra":    return r.mrr_after!=null?`<span class="num">${money(r.mrr_after)}</span>`:DASH;
    case "funding": return r.funding?`<span class="chip">${esc(fund(r.funding))}</span>`:DASH;
    case "enr":     return r.enrollees!=null?`<span class="num">${r.enrollees}</span>`:DASH;
    case "carrier": { const ml=medLine(r); if(!ml||!ml.carrier) return DASH;
                      return `<span title="medical carrier">${esc(ml.carrier)}${ml.state?` <span class="t-ok">(${esc(ml.state)})</span>`:""}</span>`; }
    case "packets":{ const p=r.packets_files; return p==null?DASH:`<span class="num" title="${esc(r.packet_carriers||"")}">${p}</span>`; }
    case "nlines":  return `<span class="nlines" data-lines="1" title="Expand per-benefit enrolled columns"><span class="dot ${LINES_OPEN?"on":""}"></span> ${r.num_lines??0} ▸</span>`;
    case "lf":      return r.lf_quote?`<span class="badge rc" title="${esc(r.lf_quote)}">LF</span>`:DASH;
    case "lfsav":   { const b=r.lf_savings_band; if(!b) return DASH;
                      const cls={High:"lfs-hi",Medium:"lfs-md",Low:"lfs-lo",No:"lfs-no"}[b]||"lfs-no";
                      const pct=r.lf_savings_pct!=null?` · ${(r.lf_savings_pct*100).toFixed(0)}%`:"";
                      return `<span class="lfsav ${cls}" title="LF savings ${b}${pct} vs current">${b}</span>`; }
    case "recert":  return hasRecert(r)?`<span class="badge rc" title="${esc(r.recert_status||"recert")}">${esc(r.recert_status||"Recert")}</span>`:DASH;
    case "sep":     return isY(r.sep)?dot("bad","SEP on the opp"):DASH;
    case "bor":     return isY(r.bor_term)?dot("bad","BoR / termination"):DASH;
    case "rate":    return rateCell(r);
    case "autoren": return isY(r.auto_renewal)?`<span title="Customer auto-renewed — confirmed default &amp; skipped flow${r.auto_renewal_date?" ("+esc(r.auto_renewal_date)+")":""}">${dot("on","Auto-renewal")}</span>`:DASH;
    case "defauto": return isY(r.default_automation)?dot("on","Default automation"+(r.default_automation_date?" · completed "+r.default_automation_date:"")):DASH;
    case "intro":   return isY(r.intro_call)?`<span title="Intro complete${r.intro_call_date?" "+esc(r.intro_call_date):""}">${dot("on","Intro call complete")}</span>`:DASH;
    case "introc":  return isY(r.intro_connect)?`<span title="Live connect${r.intro_connect_date?" "+esc(r.intro_connect_date):""}">${dot("on","Intro connected")}</span>`:( r.intro_connect==null?DASH:`<span title="no live connect">${dot("warn","no live connect logged")}</span>`);
    case "lastupd": { const dt=r.last_call_date; if(!dt) return DASH;
                    const tag=callDispTag(r.last_call_disp);
                    return `<span class="num" title="last call ${esc(dt)}${tag?" · "+esc(tag):""}">${mdShort(dt)}${tag?` <span class="t-ok">· ${esc(tag)}</span>`:""}</span>`; }
    case "emaildue":if(r.email_due==null) return DASH;
                    if(!isY(r.email_due)) return `<span class="t-ok">N</span>`;
                    { const aging=/missed|aging/i.test(r.email_due_status||"");
                      const dd=r.email_due_hoop_days;
                      const val=dd!=null?dd+"d":(r.email_due_hoop_hrs!=null?r.email_due_hoop_hrs+"h":"due");
                      return `<span class="pend" title="Latest inbound pending · ${esc(r.email_due_status||"pending")}${dd!=null?` · ${dd}d HOOP`:""}"><span class="dot"></span><span class="num ${aging?"t-bad":""}">${val}${aging?" ⚠":""}</span></span>`; }
    case "emailrecv":return r.email_received_date?`<span class="num" title="latest unanswered inbound received">${esc(r.email_received_date)}</span>`:DASH;
    case "lastout":{ const dt=r.last_outbound_email_date; if(!dt) return DASH; const d=dUntil(dt); const ago=d==null?null:-d;
        return `<span class="num ${ago!=null&&ago>14?"t-bad":ago!=null&&ago>7?"t-warn":""}" title="our last outbound email: ${esc(dt)}">${ago!=null?ago+"d":esc(dt)}</span>`; }
    case "lastin":{ const dt=r.last_inbound_email_date; if(!dt) return DASH; const d=dUntil(dt); const ago=d==null?null:-d;
        return `<span class="num ${ago!=null&&ago>21?"t-bad":ago!=null&&ago>14?"t-warn":""}" title="customer's last inbound email: ${esc(dt)}">${ago!=null?ago+"d":esc(dt)}</span>`; }
    case "survcount":{ const n=r.all_survey_count; return (n!=null&&n>0)?`<span class="num" title="surveys in trailing 12 months">${n}</span>`:DASH; }
    case "recsent": return r.default_rec_sent?`<span class="num">${esc(r.default_rec_sent)}</span>`:DASH;
    case "d2def":   { const d=r.days_to_rec_cycle; return d==null?DASH:`<span class="num" title="opp create → first recommendation sent">${Math.round(+d)}d</span>`; }
    case "trfd":    { const d=r.days_to_default; return d==null?DASH:`<span class="num ${d>5?"t-warn":""}" title="Time in RFD (SLO) — days in Ready-for-Default-Package">${d.toFixed(1)}d</span>`; }
    case "altreq":  { const y = isY(r.alt_requested) || !!r.alt_requested_date;
                      return y ? dot("on","Alternates requested (date in drill-down)") : DASH; }
    case "altcreated":{ const n=r.alt_created;
                      if (n==null) return DASH;
                      return n>0 ? `<span class="num" title="draft alternate packages created (dates in drill-down)">${n}</span>` : `<span class="t-ok" title="no draft alternate packages">0</span>`; }
    case "altpub":  return r.alt_published_date?`<span class="num" title="first non-default package published">${esc(r.alt_published_date)}</span>`:DASH;
    case "days2alt":{ const d=r.days_to_alt; if(d==null) return DASH;
                      const noAlt = !isY(r.alt_requested) && !r.alt_requested_date;
                      if(d===0 && noAlt) return `<span class="t-ok" title="no alternate requested">0</span>`;
                      return `<span class="num" title="elapsed days to alt published · ${esc(r.alt_published_basis||"")}">+${d}d</span>`; }
    case "terc":    { const d=r.time_in_erc; return d==null?DASH:`<span class="num ${(+d)>5?"t-warn":""}" title="Time in ER Confirm — days in stage">${(+d).toFixed(1)}d</span>`; }
    case "tix":     return `<span class="num ${(r.tickets_to_advising||0)>=2?"t-warn":""}">${r.tickets_to_advising??0}</span>`;
    case "opentix":   { const n=r.open_tickets; return n==null?DASH:`<span class="num ${n>=1?"t-warn":""}" title="open tickets — status not Closed/Resolved">${n}</span>`; }
    case "opentixsla":{ const n=r.open_tickets_past_sla; return n==null?DASH:`<span class="num ${n>=1?"t-bad":""}" title="open tickets older than 5 days (past SLA)">${n}</span>`; }
    case "bostatus":return r.bo_status?`<span class="chip">${esc(r.bo_status)}</span>`:DASH;
    case "inapp":   return r.inapp_current!=null?`<span class="num">${esc(r.inapp_current)}</span>`:DASH;
    case "csat":    return r.csat_current!=null?`<span class="num">${esc(r.csat_current)}</span>`:DASH;
  }
  return DASH;
}

/* ============================================================ kpis */
function renderKpis(){
  const rs = filtered();
  // Per-tab tiles: Total opps · Total MRR (before on Open/PF, after on Closed) · # At risk (High)
  const isClosedTab = TAB==="closed";
  const sumF = f => rs.reduce((a,r)=>{ const v=r[f]; return a + (v==null?0:v); }, 0);
  const atRisk = rs.filter(r=>riskCached(r).tier==="High").length;
  const cards = [ ["kpi", "Opps", rs.length.toLocaleString(), "in this tab (after filters)", false] ];
  if (isClosedTab){
    cards.push(["kpi tealk", "MRR before", money(sumF("mrr_before")), "sum across filtered rows", true]);
    cards.push(["kpi tealk", "MRR after", money(sumF("mrr_after")), "sum across filtered rows", true]);
  } else {
    cards.push(["kpi tealk", "MRR (before)", money(sumF("mrr_before")), "sum across filtered rows", true]);
  }
  cards.push(["kpi accent", "At risk (High)", atRisk.toLocaleString(), "High-risk rows in this tab", false]);
  el("kpis").innerHTML = cards.map(([cls,l,v,s,mono]) =>
    `<div class="${cls}"><div class="lbl">${l}</div><div class="val${mono?" mono":""}">${v}</div><div class="sub2">${s}</div></div>`).join("");
}

/* ============================================================ filters */
const SEL = { adv:new Set(), pe:new Set(), stage:new Set(), tier:new Set(), cohort:new Set(), risk:new Set() };
let DROPS = {};
function multiDrop(mountId, label, items, sel, onChange){
  const mount = el(mountId); if (!mount) return null;
  mount.className = "md";
  mount.innerHTML =
    `<label>${esc(label)}</label>` +
    `<div class="md-trig"><span class="md-sum"></span><span class="md-car">▸</span></div>` +
    `<div class="md-pop hidden">` +
      `<div class="md-actions">` +
        `<button type="button" class="md-btn md-all">All</button>` +
        `<button type="button" class="md-btn md-none">None</button>` +
        `<span class="md-count"></span></div>` +
      `<div class="md-searchwrap"><input type="text" class="md-search" placeholder="Search…"></div>` +
      `<div class="md-list"></div>` +
    `</div>`;
  const sum=mount.querySelector(".md-sum"), car=mount.querySelector(".md-car"),
        trig=mount.querySelector(".md-trig"), pop=mount.querySelector(".md-pop"),
        allB=mount.querySelector(".md-all"), noneB=mount.querySelector(".md-none"),
        cnt=mount.querySelector(".md-count"), searchI=mount.querySelector(".md-search"),
        list=mount.querySelector(".md-list");
  let open=false, q="";
  const summary=()=>{ const n=sel.size, t=items.length;
    if (n===t) return "All"; if (n===0) return "None";
    if (n===1){ const k=[...sel][0], it=items.find(x=>x.key===k); return it?it.label:"1 selected"; }
    return n+" selected"; };
  function syncHead(){
    sum.textContent=summary(); car.textContent=open?"▾":"▸";
    cnt.textContent=sel.size+"/"+items.length;
    allB.classList.toggle("on", sel.size===items.length);
    noneB.classList.toggle("on", sel.size===0);
    mount.classList.toggle("md-active", sel.size!==items.length);
  }
  const rowHtml=it=>{ const on=sel.has(it.key);
    return `<label class="md-row"><input type="checkbox" data-k="${esc(it.key)}"${on?" checked":""}>` +
      `<span class="md-rl">${esc(it.label)}</span>${on?'<span class="md-ck">✓</span>':""}</label>`; };
  function renderList(){
    const ql=q.toLowerCase(), match=it=>!ql||it.label.toLowerCase().includes(ql);
    const selI=items.filter(it=>sel.has(it.key)&&match(it));
    const unselI=items.filter(it=>!sel.has(it.key)&&match(it));
    let h="";
    if (selI.length) h+=`<div class="md-grp">Selected (${selI.length})</div>`+selI.map(rowHtml).join("");
    h+=unselI.map(rowHtml).join("");
    if (!selI.length && !unselI.length) h+=`<div class="md-empty">${q?"No matches":"None available"}</div>`;
    list.innerHTML=h;
  }
  const sync=()=>{ syncHead(); renderList(); };
  function setOpen(o){ open=o; pop.classList.toggle("hidden",!open); car.textContent=open?"▾":"▸";
    if (open){ q=""; searchI.value=""; renderList(); setTimeout(()=>searchI.focus(),0); } }
  trig.addEventListener("click", e=>{ e.stopPropagation(); setOpen(!open); });
  allB.addEventListener("click", e=>{ e.stopPropagation(); items.forEach(it=>sel.add(it.key)); sync(); onChange(); });
  noneB.addEventListener("click", e=>{ e.stopPropagation(); sel.clear(); sync(); onChange(); });
  searchI.addEventListener("input", ()=>{ q=searchI.value; renderList(); });
  list.addEventListener("change", e=>{ const cb=e.target.closest("input[type=checkbox]"); if(!cb) return;
    const k=cb.dataset.k; if (cb.checked) sel.add(k); else sel.delete(k); syncHead(); renderList(); onChange(); });
  pop.addEventListener("mousedown", e=>e.stopPropagation());
  document.addEventListener("mousedown", e=>{ if (open && !mount.contains(e.target)) setOpen(false); });
  sync();
  return { sync, items, sel, mount };
}
function buildFilters(){
  const mk=(keyFn,labFn,sortFn)=>{ const m=new Map();
    HUB.forEach(r=>{ const k=keyFn(r); if(!m.has(k)) m.set(k, labFn(k)); });
    return [...m.entries()].map(([key,label])=>({key,label})).sort(sortFn); };
  const byLabel=(a,b)=>a.label.localeCompare(b.label);
  const advI = mk(r=>r.advisor||"",        k=>k||"—", byLabel);
  const peI  = mk(r=>r.pe||"",             k=>k||"—", byLabel);
  const stI  = mk(r=>r.stage||"",          k=>k||"—", byLabel);
  const tiI  = (()=>{ const m=new Map();
    HUB.forEach(r=>{ if(r.queue_tier==null) return; const k=String(r.queue_tier); if(!m.has(k)) m.set(k,"P"+k); });
    return [...m.entries()].map(([key,label])=>({key,label})).sort((a,b)=>(+a.key)-(+b.key)); })();
  const coI  = mk(r=>r.cohort||"",         k=>k?cohortLabel(k):"—", (a,b)=>a.key.localeCompare(b.key));
  const seedAll=(set,items)=>{ set.clear(); items.forEach(i=>set.add(i.key)); };
  seedAll(SEL.adv,advI); seedAll(SEL.pe,peI); seedAll(SEL.stage,stI); seedAll(SEL.tier,tiI); seedAll(SEL.cohort,coI);
  const onChange=()=>{ OPEN=null; PAGE=1; persist(); render(); };
  DROPS.adv    = multiDrop("mdAdv",   "Advisor",         advI, SEL.adv,    onChange);
  DROPS.pe     = multiDrop("mdPE",    "PE",              peI,  SEL.pe,     onChange);
  DROPS.stage  = multiDrop("mdStage", "Stage",           stI,  SEL.stage,  onChange);
  DROPS.tier   = multiDrop("mdTier",  "Outreach priority",tiI,  SEL.tier,   onChange);
  DROPS.cohort = multiDrop("mdCohort","Cohort · Renewal",coI,  SEL.cohort, onChange);
  const riskItems=[{key:"High",label:"High"},{key:"Med",label:"Medium"},{key:"Low",label:"Low"}];
  SEL.risk.clear(); riskItems.forEach(i=>SEL.risk.add(i.key));
  DROPS.risk = multiDrop("mdRisk","Risk",riskItems,SEL.risk,onChange);
}
function filtered(){
  const q = el("fSearch").value.trim().toLowerCase();
  const riskOk = r => SEL.risk.has(riskCached(r).tier);
  const S = SEL;
  return rows().filter(r =>
    S.adv.has(r.advisor||"") && S.pe.has(r.pe||"") && S.stage.has(r.stage||"") &&
    (r.queue_tier==null || S.tier.has(String(r.queue_tier))) && S.cohort.has(r.cohort||"") && riskOk(r) &&
    (!q||((r.company||"")+" "+(r.advisor||"")+" "+(r.pe||"")).toLowerCase().includes(q)));
}

/* ============================================================ persisted view state (localStorage + URL hash) */
function serializeState(){
  return { tab:TAB, sort:SORT, page:PAGE, pageSize:PAGE_SIZE,
    q: el("fSearch")?el("fSearch").value:"",
    risk:[...SEL.risk],
    sel:{ adv:[...SEL.adv], pe:[...SEL.pe], stage:[...SEL.stage], tier:[...SEL.tier], cohort:[...SEL.cohort] } };
}
function persist(){
  try{
    const s = JSON.stringify(serializeState());
    localStorage.setItem(LS_KEY, s);
    history.replaceState(null, "", "#advhub=" + encodeURIComponent(s));
  }catch(e){ /* storage/history may be unavailable */ }
}
function restoreState(){
  let s = null;
  try{
    const m = /[#&]advhub=([^&]+)/.exec(location.hash||"");
    if (m) s = JSON.parse(decodeURIComponent(m[1]));
    if (!s){ const raw = localStorage.getItem(LS_KEY); if (raw) s = JSON.parse(raw); }
  }catch(e){ s = null; }
  if (!s) return;
  try{
    if (s.tab && ["open","pf","closed"].includes(s.tab)){ TAB = s.tab; CLOSED = (TAB==="closed"); }
    if (s.sort && s.sort.k) SORT = s.sort;
    if (typeof s.pageSize==="number" && [50,100,250].includes(s.pageSize)) PAGE_SIZE = s.pageSize;
    if (typeof s.page==="number" && s.page>=1) PAGE = s.page;
    if (typeof s.q==="string" && el("fSearch")) el("fSearch").value = s.q;
    if (Array.isArray(s.risk)){ SEL.risk.clear(); s.risk.forEach(k=>SEL.risk.add(k)); }
    if (s.sel){
      const apply = (set,arr) => { if (Array.isArray(arr)){ set.clear(); arr.forEach(k=>set.add(k)); } };
      apply(SEL.adv,s.sel.adv); apply(SEL.pe,s.sel.pe); apply(SEL.stage,s.sel.stage);
      apply(SEL.tier,s.sel.tier); apply(SEL.cohort,s.sel.cohort);
    }
  }catch(e){ /* ignore malformed state */ }
}

/* ============================================================ table render */
function render(){
  renderKpis();
  const vc = visibleCols();
  const pinAttr = (c,i) => {
    if (!c.pin) return {cls:c.line?"g-line":"", style:""};
    const left = pinLeft(vc,i), w = PIN_W[c.k]||120, last = !(vc[i+1] && vc[i+1].pin);
    return {cls:"pin"+(last?" shadow":""), style:`left:${left}px;min-width:${w}px;max-width:${w}px`};
  };
  let bands = [], i=0;
  while (i<vc.length){
    const g = vc[i].g, start=i; let span=0;
    while (i<vc.length && vc[i].g===g){ span++; i++; }
    const pin = vc[start].pin ? ` pin shadow` : "";
    const style = vc[start].pin ? ` style="left:0"` : "";
    bands.push(`<th colspan="${span}" class="g-${g}${pin}"${style}>${GROUP_LABEL[g]}</th>`);
  }
  el("grpRow").innerHTML = bands.join("");
  el("hdr").innerHTML = vc.map((c,i) => {
    const a = pinAttr(c,i), arrow = SORT.k===c.k ? (SORT.dir<0?" ↓":" ↑") : "";
    const tip = c.ttl ? c.ttl() : "";
    const label = typeof c.t==="function" ? c.t() : c.t;
    return `<th data-k="${c.k}" class="${a.cls}${c.line?" g-line":""}" style="${a.style}"${tip?` title="${esc(tip)}"`:""}>${label}${arrow}</th>`;
  }).join("");
  el("hdr").querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
    const k = th.dataset.k;
    const asc = ["advisor","pe","company","stage","renewal","seldl","subdl","funding","lastupd","altreqd","closedon","bostatus","carrier","outcome"].includes(k);
    SORT = (SORT.k===k) ? {k,dir:-SORT.dir} : {k,dir:asc?1:-1};
    PAGE = 1; persist();     // re-sort operates on the full set; reset to first page
    render();
  }));
  const col = COLS.find(c=>c.k===SORT.k) || COLS[0];
  const data = filtered().slice().sort((a,b) => {
    const x=col.s(a), y=col.s(b);
    const xn=(x==null), yn=(y==null);
    if (xn||yn){ if(xn&&yn) return (a.company||"").localeCompare(b.company||""); return xn?1:-1; }
    if (x===y) return (a.company||"").localeCompare(b.company||"");
    return (x>y?1:-1)*SORT.dir;
  });
  // ---- pagination over the full filtered+sorted set (only current page enters the DOM) ----
  const total = data.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (PAGE > pages) PAGE = pages;
  if (PAGE < 1) PAGE = 1;
  const start = (PAGE-1)*PAGE_SIZE;
  const end   = Math.min(total, PAGE*PAGE_SIZE);
  const shown = data.slice(start, end);
  el("body").innerHTML = shown.length ? shown.map(r =>
    `<tr class="row${OPEN===r.opp_id15?" open":""}" data-id="${esc(r.opp_id15)}">` +
      vc.map((c,i)=>{const a=pinAttr(c,i);const cv=cell(r,c.k);return `<td class="${a.cls}${c.line?" g-line":""}" style="${a.style}">${(cv===""||cv==null)?DASH:cv}</td>`;}).join("") + `</tr>` +
      (OPEN===r.opp_id15 ? detailRow(r,vc.length) : "")
  ).join("") : `<tr><td class="loading" colspan="${vc.length}">Nothing matches these filters.</td></tr>`;
  el("body").querySelectorAll("tr.row").forEach(tr => tr.addEventListener("click", e => {
    if (e.target.closest("a")) return;
    if (e.target.closest("[data-lines]")) return;
    const id = tr.dataset.id;
    OPEN = (OPEN===id) ? null : id;
    render();
  }));
  el("body").querySelectorAll("[data-lines]").forEach(n => n.addEventListener("click", e => {
    e.stopPropagation(); LINES_OPEN = !LINES_OPEN; render();
  }));
  const dc = el("detailCell"); if (dc) dc.addEventListener("click", e => { if(!e.target.closest("a") && !e.target.closest("th")) e.stopPropagation(); });
  const showX = total ? start+1 : 0;
  const pagi =
    `<div class="pagi">`
    + `<label>Rows per page <select id="pgSize">`
    + [50,100,250].map(n=>`<option value="${n}"${n===PAGE_SIZE?" selected":""}>${n}</option>`).join("")
    + `</select></label>`
    + `<button class="btn ghost sm" id="pgPrev"${PAGE<=1?" disabled":""}>&larr; Prev</button>`
    + `<span class="pgstat">Page <input type="text" id="pgJump" value="${PAGE}"> of ${pages.toLocaleString()}</span>`
    + `<button class="btn ghost sm" id="pgNext"${PAGE>=pages?" disabled":""}>Next &rarr;</button>`
    + `<span class="pgshow">Showing ${showX.toLocaleString()}&ndash;${end.toLocaleString()} of ${total.toLocaleString()} (filtered from ${rows().length.toLocaleString()})</span>`
    + `</div>`;
  el("foot").innerHTML = pagi
    + `<div style="margin-top:6px">Sort &amp; filters run on the full matching set; only the current page is drawn. `
    + `Every column sortable; click a row for the full record. All fields shown; blank = &mdash;.</div>`;
  // ---- wire pagination controls ----
  const pgSize = el("pgSize");
  if (pgSize) pgSize.addEventListener("change", () => { PAGE_SIZE = +pgSize.value || 100; PAGE = 1; persist(); render(); });
  const pgPrev = el("pgPrev");
  if (pgPrev) pgPrev.addEventListener("click", () => { if (PAGE>1){ PAGE--; persist(); render(); } });
  const pgNext = el("pgNext");
  if (pgNext) pgNext.addEventListener("click", () => { if (PAGE<pages){ PAGE++; persist(); render(); } });
  const pgJump = el("pgJump");
  if (pgJump){
    const jump = () => { let v = parseInt(pgJump.value,10); if (isNaN(v)) { pgJump.value = PAGE; return; }
      v = Math.max(1, Math.min(pages, v)); PAGE = v; persist(); render(); };
    pgJump.addEventListener("change", jump);
    pgJump.addEventListener("keydown", e => { if (e.key==="Enter") jump(); });
  }
  syncTopScroll();
  updateCohortPill();
  updateTabCounts();
}
function syncTopScroll(){
  const inner = el("tblTopInner"), wrap = el("tblwrap"), tbl = el("tbl");
  if (!inner || !wrap) return;
  inner.style.width = ((tbl ? tbl.scrollWidth : wrap.scrollWidth) || 0) + "px";
}
function updateCohortPill(){
  const cp = el("cohortPill"); if (!cp) return;
  const items = (DROPS.cohort && DROPS.cohort.items) || [];
  const sel = SEL.cohort, t = items.length, n = sel.size;
  let txt;
  if (!t || n===t) txt = "All cohorts";
  else if (n===0)  txt = "No cohorts";
  else if (n===1){ const k=[...sel][0]; txt = k ? `Cohort · ${cohortLabel(k)}` : "Cohort · —"; }
  else             txt = n+" cohorts";
  cp.textContent = txt;
}
function updateTabCounts(){
  const c={open:0,pf:0,closed:0}; HUB.forEach(r=>c[tabOf(r)]++);
  el("cnt-open").textContent=c.open.toLocaleString();
  el("cnt-pf").textContent=c.pf.toLocaleString();
  el("cnt-closed").textContent=c.closed.toLocaleString();
}

/* ============================================================ drill-down */
// shared line ordering for both drill tables (respects DRILL_SORT)
function drillLineRows(r){
  return (r.lines||[]).slice().sort((a,b)=>{
    const f = c => (c[DRILL_SORT.k]);
    let x=f(a), y=f(b);
    if (typeof x==="string"||typeof y==="string"){ x=x||""; y=y||""; }
    else { x=x??-Infinity; y=y??-Infinity; }
    if (x===y) return 0;
    return (x>y?1:-1)*DRILL_SORT.dir;
  });
}
// (a) Enrollment: Line · Carrier b→a · Enrolled b→a · Δ Enrolled · Packet
function drillEnrollment(r){
  const ls = drillLineRows(r);
  const cols = [["Line","","benefit_type"],["Carrier b→a","","carrier"],
                ["Enrolled b→a","r","enr_before"],["Δ Enrolled","r","enr_after"],["Packet","r","packet"]];
  let head = cols.map(([t,cls,sk])=>{ const arrow=DRILL_SORT.k===sk?(DRILL_SORT.dir<0?" ↓":" ↑"):"";
    return `<th class="${cls}" data-sk="${sk}">${t}${arrow}</th>`; }).join("");
  if (!ls.length) return `<div class="linesx"><table class="lines"><thead><tr>${head}</tr></thead><tbody><tr><td colspan="${cols.length}" class="t-ok">— no benefit lines on record —</td></tr></tbody></table></div>`;
  const body = ls.map(l => {
    const car = `${esc(l.carrier||"—")}${(l.carrier_after&&l.carrier_after!==l.carrier)?` → ${esc(l.carrier_after)}`:""}${l.state?` <span class="t-ok">(${esc(l.state)})</span>`:""}`;
    const eb=l.enr_before, ea=l.enr_after;
    const dEnr = (eb!=null&&ea!=null) ? (ea-eb) : null;
    const dStr = dEnr==null?"—":(dEnr>0?"+":"")+dEnr;
    const dCls = dEnr==null?"":dEnr<0?"t-bad":dEnr>0?"t-gold":"";
    return `<tr><td>${esc(l.benefit_type||"")}</td><td>${car}</td>`
      + `<td class="r num">${eb==null?"—":eb}→${ea==null?"—":ea}</td>`
      + `<td class="r num ${dCls}">${dStr}</td>`
      + `<td class="r ${l.packet?"chk":"chk no"}">${l.packet?"✓":"—"}</td></tr>`;
  }).join("");
  const tEnrB=(r.lines||[]).reduce((a,l)=>a+(l.enr_before||0),0);
  const tEnrA=(r.lines||[]).reduce((a,l)=>a+(l.enr_after||0),0);
  const tD=tEnrA-tEnrB;
  const nPk=(r.lines||[]).filter(l=>l.packet).length;
  const nLn=(r.lines||[]).length;
  const tot = `<tr class="tot"><td>Total</td><td>${nLn} lines</td><td class="r num">${tEnrB}→${tEnrA||"—"}</td><td class="r num">${(tD>0?"+":"")+tD}</td><td class="r num">${nPk}/${nLn}</td></tr>`;
  return `<div class="linesx"><table class="lines"><thead><tr>${head}</tr></thead><tbody>${body}${tot}</tbody></table></div>`;
}
// (b) Premium (medical first): Line · Expiring · Default · Selected · Premium Δ
//  - Default/Selected labelled "offered menu" (avg of offered plans)
//  - headline Premium Δ is medical-anchored: rate_increase_pct (Open/PF) / d_fin (Closed); non-medical -> —
//  - HSA/FSA/DCA carry no premium -> —
function drillPremium(r){
  const closed = CLOSED;
  const NOPREM = new Set(["hsa","fsa","dca"]);
  const base = drillLineRows(r);
  const med  = base.filter(l=>l.benefit_type==="medical");
  const rest = base.filter(l=>l.benefit_type!=="medical");
  const ls = med.concat(rest);
  const expField = closed ? "pr_exp_n" : "pr_exp_e";
  const menu = ` <span class="t-ok" style="font-weight:400;text-transform:none;letter-spacing:0">(offered menu)</span>`;
  const cols = [
    ["Line","","benefit_type",""],
    ["Expiring","r",expField, closed?"expiring premium (enrolled)":"expiring premium (eligible)"],
    ["Default"+menu,"r","pr_dflt","avg of offered plans"],
    ["Selected"+menu,"r","pr_sel","avg of offered plans"],
    ["Premium Δ","r prem-fin","__d__", closed?"medical final selected Δ (enrolled)":"medical projected Δ vs successor"]
  ];
  let head = cols.map(([t,cls,sk,ttl])=>{ const sortable=sk!=="__d__";
    const arrow=(sortable&&DRILL_SORT.k===sk)?(DRILL_SORT.dir<0?" ↓":" ↑"):"";
    return `<th class="${cls}"${sortable?` data-sk="${sk}"`:""}${ttl?` title="${esc(ttl)}"`:""}>${t}${arrow}</th>`; }).join("");
  if (!ls.length) return `<div class="linesx"><table class="lines"><thead><tr>${head}</tr></thead><tbody><tr><td colspan="${cols.length}" class="t-ok">— no benefit lines on record —</td></tr></tbody></table></div>`;
  const dol = (l,f) => (NOPREM.has(l.benefit_type)||l[f]==null) ? `<span class="t-ok">—</span>` : `<span class="num">${money(l[f])}</span>`;
  const premDelta = l => {
    if (l.benefit_type!=="medical") return `<span class="t-ok" title="menu blend — see Default/Selected">—</span>`;
    const v = closed ? l.d_fin : r.rate_increase_pct;
    if (v==null) return `<span class="t-ok">—</span>`;
    const cls = v>=30?"t-bad":v>=20?"t-warn":v>=15?"t-gold":"";
    return `<span class="num ${cls}">${(v>0?"+":"")+v.toFixed(1)}%</span>`;
  };
  const body = ls.map(l => `<tr><td>${esc(l.benefit_type||"")}</td>`
    + `<td class="r">${dol(l,expField)}</td>`
    + `<td class="r">${dol(l,"pr_dflt")}</td>`
    + `<td class="r">${dol(l,"pr_sel")}</td>`
    + `<td class="r prem-fin">${premDelta(l)}</td></tr>`).join("");
  return `<div class="linesx"><table class="lines"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
// all-fields policy: render every pair; blank -> em-dash. NEVER drop a row.
function kv(pairs){
  return `<div class="kv">` + pairs.map(([k,v]) => {
    const val = (v==null||v==="") ? DASH : v;
    const full = /class="verbatim"|<table|<ul/.test(String(val)) ? " full" : "";
    return `<div class="kv-row${full}"><span class="k">${esc(k)}</span><span class="v">${val}</span></div>`;
  }).join("") + `</div>`;
}
function sec(title, inner){ return `<div class="dsec"><h4>${esc(title)}</h4>${inner}</div>`; }

// renewal-cycle timeline
function drillTimeline(r){
  const steps = [
    ["Cycle open", r.tl_cycle_open, "step"],
    ["Default built", r.tl_default_built, "step"],
    ["Rec sent", r.tl_rec_sent, "step"],
    ["Alt requested", r.tl_alt_requested, "step"],
    ["Alt published", r.tl_alt_published, "step"],
    ["Selection", r.tl_selection, "step"],
    ["Renewal", r.tl_renewal, "end"]
  ];
  const endCls = r.outcome==="Won" ? " won" : ((r.outcome==="Lost"||r.outcome==="Admin") ? " lost" : "");
  return `<div class="tl">` + steps.map(([lab,dt,kind],i) => {
    const done = !!dt;
    const isEnd = kind==="end";
    const cls = "step" + (done?" done":" pending") + (isEnd?" end"+endCls:"");
    const dv = dt ? esc(dt) : "—";
    const endLbl = isEnd && r.outcome ? ` <span class="t-ok">(${esc(r.outcome==="Won"?"renewed":r.outcome.toLowerCase())})</span>` : "";
    return `<div class="${cls}"><div class="bar"></div><div class="dotm"></div>`
         + `<div class="tlab">${esc(lab)}</div><div class="tdt">${dv}${endLbl}</div></div>`;
  }).join("") + `</div>`;
}
function detailRow(r, span){
  const links = [
    r.sf_opp_url?`<a href="${esc(r.sf_opp_url)}" target="_blank" rel="noopener">Opportunity</a>`:"",
    r.hippo_url?`<a href="${esc(r.hippo_url)}" target="_blank" rel="noopener">Hippo</a>`:"",
    r.bo_url?`<a href="${esc(r.bo_url)}" target="_blank" rel="noopener">Benefit order</a>`:""
  ].filter(Boolean).join(" &middot; ") || DASH;
  const ml = medLine(r) || {};
  const dSub = dUntil(r.submission_deadline);
  const closedTab = CLOSED;

  // 2. General (incl rate structure + rating region)
  const genPairs = [
    ["Renewal date", r.renewal_date?esc(r.renewal_date):null],
    ["Cohort", r.cohort?cohortLabel(r.cohort):null],
    ["Stage", r.stage?`${esc(r.stage)}${r.days_in_stage!=null?` · ${r.days_in_stage}d in stage`:""}`:null],
    ["Selection deadline", r.selection_deadline?esc(r.selection_deadline):null],
    ["Submission deadline", r.submission_deadline?esc(r.submission_deadline):null],
    ["Days to Renewal", r.days_to_renewal!=null?`${r.days_to_renewal}d`:null],
    ["Days to Submission", dSub==null?null:(dSub<0?`${Math.abs(dSub)}d overdue`:`${dSub}d`)],
    ["Lead time", r.lead_days!=null?`${r.lead_days}d <span class="t-ok">(created→renewal)</span>`:null],
    ["Survey answered", r.survey_answered],
    ["MRR (current)", r.mrr!=null?money(r.mrr):null],
    ["Funding", r.funding?`${fund(r.funding)}${(closedTab&&r.funding_after)?` → ${fund(r.funding_after)}`:""} <span class="pill">${esc(fundTransChip(r.funding,r.funding_after))}</span>`:null],
    ["Rating", (r.rate_structure!=null||r.rating_region!=null)?`Rate structure: ${r.rate_structure!=null?esc(r.rate_structure):"—"} · Rating region: ${r.rating_region!=null?esc(r.rating_region):"—"}`:null],
    ["Contribution", r.contribution],
    ["Enrolled (med)", r.enrollees!=null?String(r.enrollees):null],
    ["Carrier (med)", ml.carrier?`${esc(ml.carrier)}${ml.state?` (${esc(ml.state)})`:""}`:null],
    ["Carriers (all)", r.carriers_enrolled],
    ["Packets", r.packets_files!=null?`${r.packets_files}${r.packet_carriers?` · ${esc(r.packet_carriers)}`:""}`:null]
  ];
  if (closedTab){
    genPairs.unshift(["Closed on", r.closed_on]);
    genPairs.unshift(["Outcome", r.outcome?`<span class="chip ${r.outcome==="Won"?"won":"lost"}">${esc(r.outcome)}</span>`:null]);
  }

  // 3. Premium & Lines
  // MRR after reconciled: prefer the row value (recomputed upstream), else sum of line mrr_after
  const sumMB = (r.lines||[]).reduce((a,l)=>a+(l.mrr_before||0),0);
  const sumMA = (r.lines||[]).reduce((a,l)=>a+(l.mrr_after||0),0);
  const mrrB = r.mrr_before!=null ? r.mrr_before : (sumMB||null);
  const mrrA = r.mrr_after!=null  ? r.mrr_after  : (sumMA||null);
  const mrrD = (mrrB!=null && mrrA!=null) ? (mrrA-mrrB) : null;
  const premMedDelta = (()=>{
    if (closedTab){ const ml=medLine(r); const v=ml?ml.d_fin:null;
      return v==null ? `<span class="pill">—</span>` : `<span class="pill ${v>=15?"hot":""}">${(v>0?"+":"")+v.toFixed(1)}% · final selected</span>`; }
    return r.rate_increase_pct!=null
      ? `<span class="pill ${r.rate_increase_pct>=15?"hot":""}">${r.rate_increase_pct.toFixed(1)}% · projected renewal (vs successor)</span>`
      : `<span class="pill">not built · ${esc(r.rate_status||"")}</span>`;
  })();
  const premPairs = [
    ["Premium Δ (medical)", premMedDelta],
    ["MRR (current)", r.mrr!=null?money(r.mrr):null],
    ["MRR before → after → Δ", (mrrB!=null||mrrA!=null)
        ? `${mrrB==null?"—":money(mrrB)} → ${mrrA==null?"—":money(mrrA)}${mrrD!=null?` · <span class="pill ${mrrD<0?"hot":""}">${(mrrD>0?"+":"")+money(mrrD)}</span>`:""}`
        : null]
  ];
  const premInner = kv(premPairs)
    + `<div class="dsec-line" style="margin-top:10px"><h4 style="border:none;padding:0;margin:0 0 4px">Enrollment${closedTab?" (before → after)":""}</h4>${drillEnrollment(r)}</div>`
    + `<div class="dsec-line" style="margin-top:12px"><h4 style="border:none;padding:0;margin:0 0 4px">Premium (medical first)</h4>${drillPremium(r)}
        <div class="foot" style="margin-top:8px">Default &amp; Selected are averages across the offered plan menu; the headline Premium Δ is medical-anchored (${closedTab?"final selected, enrolled":"projected vs successor"}). Savings accounts (HSA/FSA/DCA) carry no premium. Click a header to sort.</div></div>`;

  // 4. Flags
  const flagPairs = [
    ["Level funded", r.lf_quote?`<span class="pill hot">${esc(r.lf_quote)}</span>`:null],
    ["LF savings", r.lf_savings_band?`${esc(r.lf_savings_band)}${r.lf_savings_pct!=null?` · ${(r.lf_savings_pct*100).toFixed(1)}%`:""} vs current`:(r.lf_savings_pct!=null?`${(r.lf_savings_pct*100).toFixed(1)}% vs current`:null)],
    ["Recommended in Alt", (r.lf_quote||r.lf_savings_band)?(r.lf_in_alt==="Y"?`<span class="badge gr">Yes</span>`:`<span class="t-ok">No</span>`):null],
    ["Recert", hasRecert(r)?`<span class="pill hot">${esc(r.recert_status||"flagged")}</span>`:null],
    ["Recert flag date", r.recert_flag_date],
    ["Recert lateness", r.recert_lateness_days!=null?`${r.recert_lateness_days}d late`:null],
    ["SEP", isY(r.sep)?`<span class="pill hot">flagged</span>`:null],
    ["Auto-renewal (customer)", isY(r.auto_renewal)?`<span class="pill">Yes${r.auto_renewal_date?" · "+esc(r.auto_renewal_date):""}</span>`:null],
    ["Default automation", (()=>{
        if (!isY(r.default_automation)) return `No`;
        const dt = r.default_automation_date?` · ${esc(r.default_automation_date)}`:"";
        const elig = dot(isY(r.automation_eligible)?"on":"", "Eligible to auto-finalize");
        const rp   = dot(r.rate_parse_success==="Y"?"on":(r.rate_parse_success==="N"?"bad":""), "Rate parsing succeeded");
        return `Yes${dt} ${elig}${rp}`;
      })()],
    ["BoR / termination", isY(r.bor_term)?`<span class="pill hot">flagged</span>`:null],
    ["Blocked reason", r.blocked_reason?`<span class="pill hot">${esc(r.blocked_reason)}</span>`:null],
    ["RFD / ERC / ALT SLA", `${esc(r.rfd_sla||"na")} / ${esc(r.erc_sla||"na")} / ${esc(r.alt_sla||"na")}`]
  ];

  // 5. Recommendation
  const recPairs = [
    ["Default sent (SF)", r.default_rec_sent],
    ["Time to rec sent (create→sent)", r.days_to_rec_cycle!=null?`${Math.round(+r.days_to_rec_cycle)}d`:null],
    ["Time in RFD (SLO)", r.days_to_default!=null?`${r.days_to_default.toFixed(1)}d <span class="t-ok">days in Ready-for-Default-Package</span>`:null],
    ["Time in ERC", r.time_in_erc!=null?`${(+r.time_in_erc).toFixed(1)}d <span class="t-ok">days in ER Confirm</span>`:null],
    ["RFD → rec sent", r.rfd_to_rec_sent_days!=null?`${r.rfd_to_rec_sent_days}d`:null],
    ["Alt requested", r.alt_requested_date?`${esc(r.alt_requested_date)}${r.alt_requested_days!=null?` · +${r.alt_requested_days}d from cycle open`:""}`:null],
    ["Alt created", r.alt_created_date?`${esc(r.alt_created_date)}${r.alt_created_days!=null?` · +${r.alt_created_days}d from cycle open`:""}`:null],
    ["Alt published", r.alt_published_date?`${esc(r.alt_published_date)}${r.alt_published_days!=null?` · +${r.alt_published_days}d ${esc(r.alt_published_basis||"")}`:""}`:null]
  ];

  // 6. Customer Contact — defined below (contactPairs), placed right after General

  // 7. Sentiment — single table, newest → oldest, CSAT / CES / in-app all folded in
  const s12 = (r.surveys_12mo||[]).slice().sort((a,b)=>String(b.date||"").localeCompare(String(a.date||"")));
  let sentInner;
  if (s12.length){
    sentInner = `<table class="mini"><thead><tr><th>Survey</th><th>Date</th><th>Rating</th><th>Verbatim</th></tr></thead><tbody>`
      + s12.map(s=>`<tr><td>${esc(s.survey||"—")}</td><td>${esc(s.date||"—")}</td><td>${esc(s.rating||"—")}</td><td>${s.verbatim?esc(s.verbatim):"—"}</td></tr>`).join("")
      + `</tbody></table>`;
  } else {
    sentInner = `<div class="foot">No surveys (CSAT / CES / in-app) in the trailing 12 months.</div>`;
  }

  // 8. Benefit order
  const boPairs = [
    ["BO status", r.bo_status?`<span class="pill">${esc(r.bo_status)}</span>`:null],
    ["Benefit order", r.bo_url?`<a href="${esc(r.bo_url)}" target="_blank" rel="noopener">Open BO</a>`:null],
    ["# Tickets → advising", r.tickets_to_advising!=null?String(r.tickets_to_advising):null]
  ];
  let boInner = kv(boPairs);
  const tk = r.tickets_list||[];
  if (tk.length){
    boInner += `<table class="mini" style="margin-top:8px"><thead><tr><th>Ticket</th><th>Escalation reason</th><th>Detail</th><th>Status</th></tr></thead><tbody>`
      + tk.map(t=>`<tr><td>${t.id?`<a href="https://gusto.my.salesforce.com/${esc(t.id)}" target="_blank" rel="noopener">${esc(t.id)}</a>`:"—"}</td><td>${esc(t.reason||"—")}</td><td>${esc(t.detail||"—")}</td><td>${esc(t.status||"—")}</td></tr>`).join("")
      + `</tbody></table>`;
  } else {
    boInner += `<div class="foot" style="margin-top:6px">No Benefits-Advising tickets on record.</div>`;
  }

  // 9. Survey answers (no names)
  let survInner;
  if ((r.survey_answers||[]).length){
    survInner = `<table class="mini"><thead><tr><th>Question</th><th>Answer</th></tr></thead><tbody>`
      + r.survey_answers.map(a=>`<tr><td>${esc(a.q||"—")}</td><td>${esc(a.a||"—")}</td></tr>`).join("")
      + `</tbody></table>`;
  } else {
    survInner = `<div class="kv"><div class="kv-row full"><span class="k">Answers</span><span class="v">${DASH} <span class="t-ok">(survey ${r.survey_answered==="Y"?"answered — no structured answers on record":"not answered"})</span></span></div></div>`;
  }

  // 10. Case summary (de-identified) + cross-type open-cases breakdown
  const obt = r.open_cases_by_type || {};
  const obtEntries = Object.entries(obt);
  const openCasesVal = obtEntries.length
    ? obtEntries.map(([t,c]) => `<span class="chip">${esc(t)}: ${c}</span>`).join(" ") + ` <span class="t-ok">· ${r.open_cases_total} open total</span>`
    : DASH;
  const summInner = `<div class="summ">${r.case_summary?esc(r.case_summary):"—"}</div>`
    + `<div class="kv" style="margin-top:8px"><div class="kv-row full"><span class="k">Open cases (all types)</span><span class="v">${openCasesVal}</span></div></div>`;

  // Customer Contact (drill only — placed right after General; grid keeps the columns)
  const nAgo = dt => { if (!dt) return "—"; const ago = dayDiff(TODAY, D(dt));
    return `<span class="num">${esc(dt)}</span> <span class="t-ok">(${ago}d ago)</span>`; };
  const contactPairs = [
    ["Intro call", isY(r.intro_call)?`<span class="pill">Done${r.intro_call_date?` · ${esc(r.intro_call_date)}`:""}</span>`:`<span class="pill hot">Not done</span>`],
    ["Intro connect", isY(r.intro_connect)?`<span class="pill">Live connect${r.intro_connect_date?` · ${esc(r.intro_connect_date)}`:""}</span>`:(r.intro_connect==null?`<span class="t-ok">none</span>`:`<span class="pill">no live connect</span>`)],
    ["Last call", (()=>{ const dt=r.last_call_date; if(!dt) return "—";
        const ago=dayDiff(TODAY,D(dt)); const tag=callDispTag(r.last_call_disp);
        return `<span class="num">${esc(dt)}</span>${tag?` <span class="t-ok">· ${esc(tag)}</span>`:""} <span class="t-ok">(${ago}d ago)</span>`; })()],
    ["Last connect", nAgo(r.last_connect_date)],
    ["Last email out", nAgo(r.last_outbound_email_date)],
    ["Last email in", nAgo(r.last_inbound_email_date)],
    ["Email awaiting reply", (()=>{
        if(!isY(r.email_due)) return `<span class="t-ok">none</span>`;
        const hoop = r.email_due_hoop_days!=null?`${r.email_due_hoop_days}d HOOP`:(r.email_due_hoop_hrs!=null?`${r.email_due_hoop_hrs}h HOOP`:"—");
        return `<span class="pill hot">received ${esc(r.email_received_date||r.email_pending_date||"—")} · ${hoop} · ${esc(r.email_due_status||"pending")}</span>`;
      })()]
  ];

  const secHtml =
      sec("Overall case summary (de-identified)", summInner)
    + sec("Renewal-cycle timeline", drillTimeline(r))
    + sec("General", kv(genPairs))
    + sec("Customer Contact", kv(contactPairs))
    + sec("Survey answers", survInner)
    + sec("Premium & lines", premInner)
    + sec("Flags", kv(flagPairs))
    + sec("Recommendation", kv(recPairs))
    + sec("Sentiment", sentInner)
    + sec("Benefit order", boInner);

  // risk "why" — one highlighted sentence at the top of the drill.
  // Open: firing reasons grouped into 4 clusters. PF: flat "Driven by …" (incl. auto-renewal).
  // Closed: "Archived — " prefix + PF-style flat sentence on the frozen values.
  const rk = riskCached(r);
  const joinAnd = a => a.length<=1 ? a.join("") : a.slice(0,-1).join(", ")+" and "+a[a.length-1];
  let rkSentence;
  if (tabOf(r)==="open"){
    const firing = rk.firing||[];
    // did the "gone quiet" floor set this tier? (tier is higher than the weighted score alone would give)
    const scoreTier = rk.score>=35?"High" : rk.score>=18?"Med" : "Low";
    const RANK={Low:0,Med:1,High:2};
    const gqDrove = (rk.goneQuiet>=1) && (RANK[rk.tier] > RANK[scoreTier]);
    const gqNote = gqDrove ? ` Tier set to ${rk.tier} by "gone quiet" (${rk.goneQuiet} of 3 channels: no email 21d+, no reply, no connect).` : "";
    if (!firing.length){
      rkSentence = `${rk.tier} risk (${rk.score}). No advising-cycle risk signals — recent contact, no rate/deadline/flag issues.`;
    } else {
      const CLUSTERS = [
        ["Customer connection", ["nointro","silence","noresp","callconnect"]],
        ["Minimal SF update",   ["stagnant"]],
        ["Recommendation",      ["rate","altsla","lfpend"]],
        ["Flags",               ["termbor","sepgr","recert","packet","deadline","subdl","unworked","lategen"]]
      ];
      let parts = "";
      CLUSTERS.forEach(([label, keys]) => {
        const rs = firing.filter(s=>keys.indexOf(s.key)>=0).map(s=>esc(s.reason));
        if (!rs.length) return;
        let extra = "";
        if (label==="Minimal SF update" && r.last_update_date) extra = `, last SF update ${esc(r.last_update_date)}`;
        parts += `${esc(label)}: ${rs.join(", ")}${extra}. `;
      });
      rkSentence = `${rk.tier} risk (${rk.score} of 100).${gqNote} ${parts}`.trim();
    }
  } else {
    const rkR = rk.reasons.slice(0,4).map(esc);
    const prefix = rk.archived ? "Archived — " : "";
    rkSentence = rkR.length
      ? `${prefix}${rk.tier} risk (${rk.score} of 100). Driven by ${joinAnd(rkR)}.`
      : `${prefix}${rk.tier} risk (${rk.score}). No fulfillment risk signals — 0 open tickets, recert clear, not within 1 week of fulfillment, sentiment ok.`;
  }
  const rkLine = `<div class="summ" style="margin-bottom:2px">${rkSentence}</div>`;

  const who = `<span class="dwho">${esc(r.advisor||"—")} &middot; ${esc(r.pe||"—")}</span>`;
  return `<tr class="detail"><td colspan="${span}" id="detailCell">
    <div class="doss">
      <div class="dhead">
        <span class="dco">${esc(r.company)}</span>
        ${r.queue_tier!=null?(tabOf(r)==="open"?tierChip(r,true):`<span class="chip arch" title="archived — last outreach priority · P${r.queue_tier}">${esc(TIER_NAMES[r.queue_tier]||("P"+r.queue_tier))}</span>`):""}${r.outcome?`<span class="chip ${r.outcome==="Won"?"won":"lost"}">${esc(r.outcome)}</span>`:""}
        ${who}
        <span class="spacer"></span>
        <button class="btn sm" data-script="${esc(r.opp_id15)}">Customer Positioning &rarr;</button>
        <span class="dlinks">${links}</span>
      </div>
      <div class="dsecs">${rkLine}${secHtml}</div>
    </div></td></tr>`;
}

/* ============================================================ Customer Positioning talk track */
let SCRIPT_ROW = null;
let LAST_TABLE_TAB = "open";
const TIER_NAMES = {1:"Default Automation",2:"Level-funded available",3:"Above-market rate",4:"Data gap",5:"Selection deadline"};
const F  = v => `<strong class="fill">${esc(v)}</strong>`;
const PH = v => `<em>[${esc(v)}]</em>`;
function scriptAgenda(r){
  const a=[];
  if (isY(r.sep)) a.push("SEP");
  if (hasRecert(r)) a.push("Recert");
  if (r.rate_increase_pct!=null && r.rate_increase_pct>=15) a.push("Above-market rate");
  if (r.lf_quote) a.push("Level funded");
  if (/Renewal Packet/i.test(r.blocked_reason||"")) a.push("Packet ask");
  if (isY(r.bor_term)) a.push("BoR / termination");
  return a.length?a:["Standard renewal"];
}
function scriptVars(r){
  if (!r) return {live:false, adv:PH("advisor"), ren:PH("date"), carrier:PH("carrier"),
    range:PH("X to Y"), exact:PH("X"), sel:PH("date"), sub:PH("date"), eff:PH("effective date"), rateKnown:false, inc:null};
  const inc = r.rate_increase_pct;   // already a percentage number
  const rk = r.rate_status==="computed";
  const lo = inc==null ? null : Math.max(0, inc - (rk?1:3));
  const hi = inc==null ? null : inc + (rk?2:4);
  const ml = medLine(r)||{};
  return { live:true, r, adv:F(r.advisor||"your advisor"), ren:F(r.renewal_date||"—"),
    carrier: ml.carrier ? F(ml.carrier) : PH("carrier"), carriers: r.carriers_enrolled||"",
    range: inc==null ? PH("X to Y") : F(lo.toFixed(0)+" to "+hi.toFixed(0)),
    exact: inc==null ? PH("X") : F(inc.toFixed(1)),
    rateKnown: rk, sel: r.selection_deadline ? F(r.selection_deadline) : PH("date"),
    sub: r.submission_deadline ? F(r.submission_deadline) : PH("date"), eff:F(r.renewal_date||"—"), inc };
}
function buildScript(r){
  const v = scriptVars(r);
  const on = {
    high:   !r || (v.inc!=null && v.inc >= 15),
    sep:    !r || isY(r.sep),
    recert: !r || hasRecert(r),
    lf:     !r || !!r.lf_quote,
    k401:   !r,                       // retirement mandate not in this dataset — struck through when live
    packet: !!r && /Renewal Packet/i.test(r.blocked_reason||""),
    term:   !!r && isY(r.bor_term)
  };
  const uhc = !r || /United/i.test(v.carriers || "");
  const ml = r ? (medLine(r)||{}) : {};
  const flow = [["Value statement",true],["Upfront contract",true],["Discovery",true],["Cost preview",true],
    ["Above market*",on.high],["SEP*",on.sep],["Timeline",true],["Recert*",on.recert],
    ["Packet ask*",on.packet],["Retirement*",on.k401],["LF tease*",on.lf],["Book the next step",true]];
  let h = "";
  h += `<div class="eyebrow">Benefits Renewals Advising</div>`;
  h += `<h1>Call positioning${r ? " — "+esc(r.company) : ""}</h1>`;
  h += `<p class="sub">${r
      ? `Personalized from this opportunity's record. <strong class="fill">Indigo</strong> values are pulled from the record; <em>[bracketed]</em> values are yours to fill. Conditional modules are included or struck through based on the record.`
      : `Positioning for any renewal conversation — first call, options review, follow-up. Pick a row on the opps tab and hit <em>Customer Positioning →</em> to have the conditional modules resolved automatically. <b>Sample lines only</b> strips everything but the language, for use live on a call.`}</p>`;
  if (r){
    const dtr = r.days_to_renewal;
    h += `<div class="prep"><h4>Before you dial</h4>
      <table><tbody>
        <tr><td class="k">Outreach priority</td><td>${r.queue_tier!=null?`P${r.queue_tier} — ${esc(TIER_NAMES[r.queue_tier]||"")}`:"—"}</td>
            <td class="k">Call agenda</td><td>${esc(scriptAgenda(r).join(" · "))}</td></tr>
        <tr><td class="k">Advisor / PE</td><td>${esc(r.advisor||"—")} · ${esc(r.pe||"—")}</td>
            <td class="k">Renewal</td><td>${esc(r.renewal_date||"—")}${dtr!=null?` (${dtr}d)`:""}</td></tr>
        <tr><td class="k">Stage</td><td>${esc(r.stage||"—")} · ${r.days_in_stage==null?"—":r.days_in_stage+"d"}</td>
            <td class="k">Selection deadline</td><td>${esc(r.selection_deadline||"—")}</td></tr>
        <tr><td class="k">Carriers</td><td>${esc(r.carriers_enrolled||ml.carrier||"—")}</td>
            <td class="k">Premium Δ</td><td>${(()=>{
              if (tabOf(r)==="closed"){ const _ml=medLine(r); const v=_ml?_ml.d_fin:null;
                return v==null?"not final":`${(v>0?"+":"")+v.toFixed(1)}% · final selected`; }
              return r.rate_increase_pct!=null?`${r.rate_increase_pct.toFixed(1)}% · projected renewal (vs successor)`:"not built";
            })()}</td></tr>
        <tr><td class="k">Packets</td><td>${r.packets_files==null?"—":r.packets_files+(r.packet_carriers?" · "+esc(r.packet_carriers):"")}</td>
            <td class="k">Default rec</td><td>${r.default_rec_sent?"sent "+esc(r.default_rec_sent):(r.default_rec_built?"built "+esc(r.default_rec_built):"not built")}</td></tr>
        <tr><td class="k">Intro call</td><td>${isY(r.intro_call)?"already complete":"not complete"}${isY(r.intro_connect)?" · connected":""}</td>
            <td class="k">Email due</td><td>${isY(r.email_due)?"latest inbound pending SLA":"no reply pending"}</td></tr>
      </tbody></table>
      <div style="margin-top:9px">${r.sf_opp_url?`<a href="${esc(r.sf_opp_url)}" target="_blank" rel="noopener">Open opportunity</a>`:""}${r.hippo_url?` &middot; <a href="${esc(r.hippo_url)}" target="_blank" rel="noopener">Hippo</a>`:""}</div>
    </div>`;
  }
  h += `<div class="flowbar">` + flow.map(([n,keep],i) =>
      `<span class="${keep ? (n.endsWith("*")?"condf":"") : "skip"}">${n.replace("*","")}</span>` +
      (i<flow.length-1 ? `<span style="color:var(--g5)">→</span>` : "")).join("") +
      `<span style="width:100%;font-size:11px;color:var(--g6);margin-top:3px">${r ? "struck-through beats were dropped for this group" : "* conditional"}</span></div>`;

  h += `<div class="beat"><div class="num">1</div><h3>Open with the value statement</h3>
    <div class="meta">~20 seconds</div>
    <p class="goal">Most customers don't know Gusto assigns them a person. Say it in the first breath — it's why the call is welcome instead of annoying.</p>
    <ul class="beats"><li>Name, company, warm check-in — then stop and let them answer.</li>
      <li>State the value in customer terms: best benefits decision for their business.</li>
      <li>Claim the relationship: single point of contact through the whole process.</li></ul>
    <div class="say"><span class="lab">Sample line</span>
      "Hi ${PH("name")}, this is ${v.adv} calling from Gusto — how are you today? … Great. So the reason I'm reaching out: I'm a benefits advisor here, and I help customers make the best benefits selections for their business at renewal. Your renewal is coming up on ${v.ren}, and I'll be your point of contact for the whole process from here through your decision."</div>
    <div class="tnote"><span class="lab">Why it works:</span> "point of contact" removes their biggest fear — getting bounced around.</div></div>`;

  h += `<div class="beat"><div class="num">2</div><h3>Upfront contract</h3>
    <div class="meta">~20 seconds · Agenda, time, permission</div>
    <p class="goal">Set the frame before asking for anything. How long, what you'll cover, what happens at the end. Then get a yes.</p>
    <ul class="beats"><li>Ask for the time explicitly.</li><li>Preview the agenda in three beats.</li>
      <li>Name the outcome up front.</li><li>Get verbal agreement before moving on.</li></ul>
    <div class="say"><span class="lab">Sample line</span>
      "Do you have about ${PH("10-15")} minutes right now? … Here's what I'd like to do: ask a few questions about how this year's plan has worked for your team, walk you through what we're projecting cost-wise, and give you the timeline so you know what's coming and when. At the end I'll ask to get a follow-up on the calendar. Does that work?"</div>
    ${on.recert ? `<div class="twarn"><span class="lab">Exception:</span> this group is under recert — the tax-document ask still happens on this call even if they're short on time.</div>` : ""}</div>`;

  h += `<div class="beat"><div class="num">3</div><h3>Discovery — 3 to 5 questions</h3>
    <div class="meta">4–6 minutes</div>
    <p class="goal">Listening for three things: what drives the decision, what broke last year, who else signs off.</p>
    <div class="qgrid">
      <div class="q"><div class="qt"><span class="tag core">Core</span>"How has this year's plan worked for your team — anything you've heard from employees?"</div><div class="qw">Surfaces network gaps and whether anyone is actually unhappy.</div></div>
      <div class="q"><div class="qt"><span class="tag core">Core</span>"Is your priority holding cost flat, or protecting the plan design and network your team has?"</div><div class="qw">The most useful question on the call — it sets the direction of the build.</div></div>
      <div class="q"><div class="qt"><span class="tag core">Core</span>"Who else is involved in the final decision, and what do they care most about?"</div><div class="qw">Prevents the late-stage stall where an unseen owner reopens everything.</div></div>
      <div class="q"><div class="qt"><span class="tag opt">Optional</span>"Has anything changed with your headcount?"</div><div class="qw">Drives eligibility, participation and LF viability.${r&&r.enrollees?" Record shows "+r.enrollees+" enrolled.":""}</div></div>
      <div class="q"><div class="qt"><span class="tag opt">Optional</span>"Is there a number where the increase stops being workable?"</div><div class="qw">Gives you a real ceiling to design alternates against.</div></div>
    </div>
    <div class="tnote"><span class="lab">Technique:</span> reflect each answer back in one sentence. It proves you listened and it's what you quote in the recommendation.</div></div>`;

  h += `<div class="beat"><div class="num">4</div><h3>Weave in the cost preview</h3>
    <div class="meta">2 minutes</div>
    <p class="goal">Cost is what they've been waiting for. Get ahead of it — don't make them ask.</p>
    <ul class="beats"><li>Bridge from their answer.</li><li>Give a range, labelled as a projection.</li>
      <li>Say what's driving it.</li><li>Follow immediately with what you can do about it.</li></ul>
    <div class="say"><span class="lab">Sample line</span>
      "Based on what we're seeing, I'd project you somewhere in the ${v.range}% range on renew-as-is — driven mostly by ${PH("carrier trend / claims / group size")}. That's a projection, not final. My job between now and our next call is to build alternatives so that number isn't the only option on the table."</div>
    ${r && !v.rateKnown ? `<div class="twarn"><span class="lab">Careful:</span> this group's actual rate action is not built yet (${esc(r.rate_status||"not built")}). The range above is the carrier + state benchmark — keep the hedge in and do not quote it as theirs.</div>`
      : `<div class="twarn"><span class="lab">Don't:</span> quote a precise number you can't defend, or hedge so hard you say nothing.</div>`}`;

  if (on.high) h += `<div class="cond"><span class="badge">${r?"Included · increase "+(v.inc!=null?v.inc.toFixed(1)+"%":""):"Only if · above 15%"}</span>
      <h4>Call out that they're above market average</h4>
      <p class="trigger">Trigger: renew-as-is increase above 15%.${r&&v.inc!=null?" This group is at "+v.inc.toFixed(1)+"%.":""}</p>
      <ul class="beats"><li>Name the number, then name it as above average.</li>
        <li>Do not apologise for it or defend the carrier.</li><li>Convert it into why the options call matters.</li></ul>
      <div class="say"><span class="lab">Sample line</span>
        "I want to flag something — at ${v.exact}%, that's above the average increase we're seeing in the market right now. I'm telling you because it changes my recommendation: when an increase runs this high, staying put is usually not the best move, and it's worth genuinely looking at what else is available before you decide."</div></div>`;

  if (on.sep) h += `<div class="cond"><span class="badge">${r?"Included · SEP flagged":"Only if · off track on SEP"}</span>
      <h4>SEP — participation &amp; contribution</h4>
      <p class="trigger">Trigger: not meeting the carrier's participation and/or contribution requirements.</p>
      <ul class="beats"><li>State it as the carrier's rule, not Gusto's.</li><li>Say which one is off track.</li>
        <li>Give the two paths: get to threshold, or move to a carrier they can meet.</li><li>Tie it to the deadline.</li></ul>
      <div class="say"><span class="lab">Sample line</span>
        "One important thing on your group. ${v.carrier} requires you to meet both participation and contribution requirements for the year, and right now you're tracking under on ${PH("participation / contribution")}. So there are two paths: we get ${PH("that number")} up to where the carrier needs it, or we look at a carrier whose requirements fit how your group is set up. Neither is a problem — but we need to pick one before ${v.sel}."</div>
      <div class="twarn"><span class="lab">Don't:</span> imply the carrier might make an exception.</div></div>`;

  h += `<div class="beat"><div class="num">5</div><h3>Set expectations on timeline</h3>
    <div class="meta">1 minute · Concrete dates</div>
    <p class="goal">Give them the calendar. Uncertainty about <em>when</em> is what generates anxious inbound.</p>
    <div class="say"><span class="lab">Sample line</span>
      "Here's the timeline so you're not guessing. ${v.rateKnown ? `I have your ${v.carrier} rates already` : `I'd expect rates from ${v.carrier} around ${PH("x/xx")}`}. Once I have those, I'll build your options and we'll review them together. You'd need a final decision by ${v.sel} for everything to be in place for ${v.eff}${r&&r.submission_deadline?`, and paperwork submitted by ${v.sub}`:""}. If anything shifts, you'll hear it from me."</div>
    ${r && r.selection_deadline && dUntil(r.selection_deadline)<0 ? `<div class="twarn"><span class="lab">Heads up:</span> the selection deadline (${esc(r.selection_deadline)}) has already passed. Acknowledge it and reset expectations.</div>` : ""}</div>`;

  if (on.recert) h += `<div class="cond"><span class="badge">${r?"Included · recert flagged":"Only if · under recert"}</span>
      <h4>Recert — ${uhc?"UnitedHealthcare ":""}tax documents &amp; audit</h4>
      <p class="trigger">Trigger: the group is under recertification.</p>
      <ul class="beats"><li>Explain recert in one sentence.</li><li>Make the ask concrete — company tax documents.</li>
        <li>State the stake: passing the audit is what lets them stay put.</li><li>Get a date and a named owner.</li></ul>
      <div class="say"><span class="lab">Sample line</span>
        "There's one more piece I need, and I'm raising it early because it takes the longest. Your group is up for recertification with ${v.carrier} — before they'll renew you, they re-verify your eligibility through an audit. What I need is your company tax documents, and the group has to pass that audit to renew with ${v.carrier}. I'll email the exact list today. Who on your team would pull those? … Can we target having them back by ${PH("date")}?"</div>
      <div class="twarn"><span class="lab">Don't:</span> soften this into "when you get a chance."</div></div>`;

  if (on.packet) h += `<div class="cond"><span class="badge">Included · blocked for a renewal packet</span>
      <h4>Renewal packet ask</h4>
      <p class="trigger">Trigger: blocked as <b>${esc(r.blocked_reason||"")}</b>.</p>
      <div class="say"><span class="lab">Sample line</span>
        "One thing holding up your build on my side — I'm still waiting on your renewal packet from ${v.carrier}. I'll email the specifics today. If I can have that back by ${PH("date")} I can keep us ahead of ${v.sel}."</div></div>`;

  if (on.k401) h += `<div class="cond"><span class="badge">Only if · retirement mandate risk</span>
      <h4>Retirement — state mandate check</h4>
      <p class="trigger">Trigger: no retirement plan on file for this company and at least one state threshold met.</p>
      <p style="font-size:13px;margin:0 0 9px">Raise it as a question, never as a determination. We can see that no retirement plan runs through Gusto payroll; we cannot see a plan they hold entirely outside Gusto, and mandate thresholds count employees <em>in that state</em>.</p>
      <ul class="beats"><li>Ask whether they offer a retirement plan today — do not assume they don't.</li>
        <li>If they don't, mention their state may require one, by name.</li>
        <li>Offer to loop in the right person. Do not quote deadlines or penalties.</li></ul>
      <div class="say"><span class="lab">Sample line</span>
        "One quick unrelated thing while I have you — do you offer a retirement plan for your team today, either through Gusto or somewhere else? … Got it. The reason I ask is that ${PH("your state's program")} may apply to a business your size, and I'd rather flag it now than have you hear about it from the state. I'm not the expert on it — if it's useful I can connect you with someone here who is."</div>
      <div class="twarn"><span class="lab">Don't:</span> tell them they are non-compliant, quote a penalty, or give a deadline.</div></div>`;

  if (on.lf) h += `<div class="beat"><div class="num">6</div><h3>Tease level funded</h3>
      <div class="meta">30 seconds · Plant, don't pitch</div>
      <p class="goal">Create a reason to take the next call. You're checking eligibility, not selling.</p>
      <div class="say"><span class="lab">Sample line</span>
        "One more thing I'm doing on my end — I'm checking whether you're eligible for a level-funded quote, which for the right group can save real money against the renewal cost. Let me see where that lands, and if you're eligible we'll talk through how it works on our next call."</div>
      <div class="twarn"><span class="lab">Don't:</span> explain how level funding works here, or promise savings.</div></div>`;
  else h += `<div class="beat" style="opacity:.55"><div class="num">6</div><h3>Level funded tease — skipped</h3>
      <div class="meta">Dropped for this group</div>
      <p class="goal">Nothing on the record suggests a level-funded path (funding: ${esc(r&&r.funding||"not set")}).</p></div>`;

  h += `<div class="beat"><div class="num">7</div><h3>Close by booking the next step</h3>
    <div class="meta">1 minute · Never end without a date</div>
    <p class="goal">The call is only successful if there's a calendar invite.</p>
    <ul class="beats"><li>Recap what you're doing next in one sentence.</li><li>Offer two concrete windows.</li>
      <li>Confirm attendees — pull in the decision-maker they named.</li><li>Confirm the invite goes out today.</li></ul>
    <div class="say"><span class="lab">Sample line</span>
      "So on my side: I'm pulling your rates, building your options${on.lf?", and checking level-funded eligibility":""}. When can we get a call scheduled to review those together? I have ${PH("day, time")} or ${PH("day, time")} — which works better? … And should we include ${PH("decision-maker")}? I'll send the invite today with my direct line in it."</div>
    <div class="tnote"><span class="lab">If they won't commit:</span> "No problem — I'll send an invite for ${PH("day")} as a placeholder and you can move it, so it doesn't fall through the cracks while rates are landing."</div></div>`;

  if (on.term) h += `<div class="cond" style="border-color:var(--coral);background:var(--coral-20)">
      <span class="badge" style="background:var(--coral-dk)">Advisor heads-up · not customer language</span>
      <h4>This opp is blocked as ${esc(r.blocked_reason||"BoR / termination")}</h4>
      <p class="trigger">A termination or BOR-away block changes this from renewal planning to retention.</p>
      <p style="font-size:13px;margin:0">Do not run the cost-preview track cold. Confirm internally what the block is, then decide whether this is a save conversation or a clean handoff. Nothing in the language above is written for that.</p></div>`;

  const objs = [
    [true, `"Just email me the rates."`, `They're avoiding a sales call. Agree to send it — and attach a reason the call earns its slot.`,
      `"Absolutely, I'll put it in writing either way. The reason I push for the call is that renew-as-is is usually the most expensive option on the page — the alternatives are where the money is, and those are hard to read cold in an email."`],
    [true, `"We're already working with a broker."`, `Don't compete. Position as no-cost extra leverage.`,
      `"That's totally fine, and I'm not asking you to drop anyone. Since your plan runs through Gusto, I'm building your renewal options regardless and there's no extra cost. Worst case you get a second set of numbers to hold theirs up against."`],
    [on.high, `"That increase is way too high."`, `Validate first. Don't defend the carrier. Convert it into direction.`,
      `"I hear you, and that reaction is fair — it's exactly why I called now instead of three weeks from now. That number is the do-nothing option. Tell me what would actually be workable and I'll build toward it."`],
    [true, `"We're probably just going to renew as-is."`, `Make the review cheap rather than arguing.`,
      `"That may well be the right call, and if it is I'll tell you so. It costs you one short call to confirm you're not leaving money on the table."`],
    [true, `"I'm not the one who decides this."`, `Get the name and get them on the next call.`,
      `"Good to know — who owns that decision? I'd still walk you through it so you're not the messenger for something you haven't seen, and we get ${PH("owner")} on the options call."`],
    [true, `"Now's not a good time."`, `Take the exit, but leave with a date.`,
      `"No problem at all. Your decision deadline is ${v.sel}, so I'd rather catch you well before then than after. Is ${PH("day")} morning or afternoon better for a quick ${PH("15")} minutes?"`],
    [on.sep, `"Can't the carrier make an exception on participation?"`, `No. Be clear, then move to the two paths.`,
      `"It's a carrier requirement for the year, not a Gusto rule, and it isn't something they waive. But it is fixable — either we get ${PH("participation / contribution")} to their threshold, or we find a carrier whose requirements fit your group better."`],
    [on.recert, `"Why does the carrier need our tax documents?"`, `Normalise it, then restate the stake and the date.`,
      `"It's a standard recertification — they re-verify eligibility before renewing, and the tax documents are how they do it. Routine, but not optional: passing the audit is what lets you renew with ${v.carrier}."`],
    [on.lf, `"What is level funding?"`, `One plain sentence, hold the rest for the next call.`,
      `"Short version: instead of paying a flat premium, you fund your own expected claims with stop-loss protection, and if your group runs healthy you can get money back. It's not right for everyone, which is why I check eligibility first."`]
  ].filter(o => o[0]);

  h += `<section class="block"><h2>Objection handling</h2>
    <p class="sub">Acknowledge → reframe → redirect. Never argue the objection head-on.${r?" Only the objections relevant to this group are shown.":""}</p>`
    + objs.map(([,q,ctx,say]) => `<details class="obj"><summary>${q}</summary><div class="body">${ctx}
        <div class="say"><span class="lab">Sample line</span>${say}</div></div></details>`).join("") + `</section>`;

  h += `<section class="block"><h2>Voicemail &amp; no-answer</h2>
    <p class="sub">Under 30 seconds. One reason to call back, one date, your direct line twice.</p>
    <div class="vm">
      <p><b>First attempt:</b> "Hi ${PH("name")}, this is ${v.adv} at Gusto — I'm the benefits advisor assigned to your renewal on ${v.ren}, and I'll be your point of contact. I've got an early read on where your rates are landing and a couple of options worth looking at before you decide. Best number is ${PH("phone")} — that's ${PH("phone")}. I'll follow up by email today."</p>
      <p><b>Second attempt (3–4 days later):</b> "Hi ${PH("name")}, ${v.adv} at Gusto again on your ${v.ren} renewal. Your decision deadline is ${v.sel} and I want to make sure you're not seeing your options for the first time on a deadline. Even 15 minutes helps. ${PH("phone")}."</p>
    </div></section>`;

  h += `<section class="block"><h2>Call hygiene</h2><div class="dontlist">
    <div class="do"><h5>Do</h5><ul>
      <li>Say "point of contact" in the first 20 seconds.</li><li>Ask for the time before you use it.</li>
      <li>Give cost as a labelled range, unprompted.</li><li>Give real dates, not "soon".</li>
      ${on.high?`<li>Flag above-15% as above market average, unprompted.</li>`:""}
      ${on.recert?`<li>Ask for recert documents on the call, with a date and a named owner.</li>`:""}
      <li>End with a calendar hold, every time.</li>
      <li>Log the priority, the ceiling, the decision-maker and any flags in Salesforce, and tick <b>Intro Call Completed</b>.</li>
    </ul></div>
    <div class="dont"><h5>Don't</h5><ul>
      <li>Run full discovery on someone who said they're short on time.</li>
      <li>Quote a precise renewal number you can't defend.</li><li>Promise level-funded savings or eligibility.</li>
      <li>Defend the carrier's increase.</li>
      ${on.sep?`<li>Suggest the carrier might waive a participation requirement.</li>`:""}
      <li>Compete with their broker.</li><li>End on "I'll follow up" with no date.</li>
    </ul></div></div></section>`;

  h += `<div class="foot" style="margin-top:26px">Sample language only. Contact names and phone numbers are placeholders by design — the Hub does not surface customer PII in the talk track.</div>`;
  return h;
}
function renderScript(){
  const r = SCRIPT_ROW;
  el("scriptDoc").innerHTML = buildScript(r);
  el("scriptDoc").classList.toggle("sampleonly", el("tSample").checked);
  el("scriptWho").innerHTML = r
    ? `Personalized for <b>${esc(r.company)}</b> — ${esc(r.advisor||"—")} · renewal ${esc(r.renewal_date||"—")}`
    : `Generic positioning. Open a row and hit <b>Customer Positioning →</b> to personalize it.`;
  el("bGeneric").classList.toggle("hidden", !r);
}
function openScript(id){
  SCRIPT_ROW = HUB.find(x=>x.opp_id15===id) || null;
  showTab("script");
}
/* type-ahead customer lookup over all HUB rows (client-side) */
const SCRIPT_LOOKUP = new Map();   // datalist value -> opp_id15
function buildScriptSearch(){
  const dl = el("scriptCompanies"), inp = el("scriptSearch");
  if (!dl || !inp) return;
  SCRIPT_LOOKUP.clear();
  const seen = new Map();
  const opts = HUB.slice()
    .sort((a,b)=>(a.company||"").localeCompare(b.company||""))
    .map(r=>{
      const base = r.company || "(no name)";
      const n = seen.get(base)||0; seen.set(base, n+1);
      // disambiguate duplicate company names by appending PE/advisor + opp id
      const val = n ? `${base} · ${r.pe||r.advisor||""} · ${r.opp_id15}` : base;
      SCRIPT_LOOKUP.set(val, r.opp_id15);
      if (!n) SCRIPT_LOOKUP.set(base, r.opp_id15);   // plain name -> first occurrence
      return `<option value="${esc(val)}"></option>`;
    });
  dl.innerHTML = opts.join("");
  const pick = ()=>{ const id = SCRIPT_LOOKUP.get(inp.value.trim()); if (id) openScript(id); };
  inp.addEventListener("change", pick);
  inp.addEventListener("input", pick);
}

/* ============================================================ Overview tab */
let OVSCOPE = {mode:"team", peSel:new Set(), icSel:new Set()};
let OVSTAGE = null;                 // null=all · "open" · "pf" · "closed" — stage-tile filter
let OVRISK  = {open:null, pf:null}; // expanded risk tier per box ("High"/"Med"/"Low"/null)
const OV_TIER_LABEL = {1:"Default Automation",2:"Level-funded available",3:"Above-market rate",4:"Data gap",5:"Selection deadline"};
const OV_HI="#c0392b", OV_MED="#e0a83e", OV_LO="#5aa87f";
const OV_PF_FACTORS = [
  ["autoren",  "Auto-renewing into increase"],
  ["ticket",   "OA→Advising tickets"],
  ["recert",   "Recert still open"],
  ["within1wk","Within 1 wk fulfillment"],
  ["sentiment","Negative in-app sentiment"]
];
// factor key -> label maps for the Overview risk boxes
const OV_OPEN_FACTOR_LABEL = {
  nointro:"Intro call not complete", silence:"No recent email outreach", noresp:"No recent customer response",
  callconnect:"No recent call connects",
  rate:"Rate increase", stagnant:"Days in SFDC stage", deadline:"Selection deadline",
  unworked:"Unworked close to renewal", lategen:"Late-generated opp", packet:"Renewal packet missing",
  recert:"Recertification", lfpend:"Level-funded quote pending", termbor:"Blocked: term/BOR away",
  subdl:"Submission deadline", altsla:"Alternates Requested > 3d", sepgr:"SEP / GR"
};
const OV_PF_FACTOR_LABEL = {
  autoren:"Auto-renewing into increase", ticket:"OA→Advising tickets",
  within1wk:"Within 1 wk fulfillment", recert:"Recert still open",
  sentiment:"Negative in-app sentiment"
};
// small local stats helpers for the insights column
const daysSince = s => { const d=dUntil(s); return d==null?null:-d; };
const median = arr => {const a=arr.filter(x=>x!=null).sort((x,y)=>x-y); return a.length?a[Math.floor((a.length-1)/2)]:null;};
function ovPEs(){ return [...new Set(HUB.map(r=>r.pe).filter(Boolean))].sort((a,b)=>a.localeCompare(b)); }
function ovICs(pe){ return [...new Set(HUB.filter(r=>!pe||r.pe===pe).map(r=>r.advisor).filter(Boolean))].sort((a,b)=>a.localeCompare(b)); }
function ovRows(){
  if (OVSCOPE.mode==="pe") return HUB.filter(r => OVSCOPE.peSel.size===0 ? false : OVSCOPE.peSel.has(r.pe));
  if (OVSCOPE.mode==="ic") return HUB.filter(r => OVSCOPE.icSel.size===0 ? false : OVSCOPE.icSel.has(r.advisor));
  return HUB.slice();
}
function ovStageSplit(rows){
  const g = {open:[], pf:[], closed:[]};
  rows.forEach(r => { const t=tabOf(r); (g[t]||g.open).push(r); });
  return g;
}
function ovScopeBar(){
  const chip=(m,lab)=>`<button class="ov-chip${OVSCOPE.mode===m?" on":""}" data-ovmode="${m}">${lab}</button>`;
  let sel="";
  if (OVSCOPE.mode==="pe") sel=`<div class="ov-scopesel" id="ovPeDrop"></div>`;
  else if (OVSCOPE.mode==="ic") sel=`<div class="ov-scopesel" id="ovIcDrop"></div>`;
  return `<div class="ov-scopebar"><div class="ov-chips">${chip("ic","IC")}${chip("pe","PE")}${chip("team","Team-wide")}</div>${sel}</div>`;
}
function ovStageCards(g){
  const sumB = arr => arr.reduce((a,r)=>a+(r.mrr_before||0),0);
  const sumA = arr => arr.reduce((a,r)=>a+(r.mrr_after||0),0);
  const hi   = arr => arr.filter(r=>riskCached(r).tier==="High");
  const cls  = stage => `ov-card ov-card-click${OVSTAGE===stage?" ov-card-on":""}`;
  const live = (label, stage, arr) => {
    const n=arr.length, h=hi(arr), pct=n?Math.round(100*h.length/n):0;
    return `<div class="${cls(stage)}" data-ovstage="${stage}" title="Click to focus the Overview on ${label}${OVSTAGE===stage?" (click again to clear)":""}"><div class="ov-card-h">${label}</div>`+
      `<div class="ov-card-n">${n.toLocaleString()} <span class="ov-card-u">opps</span></div>`+
      `<div class="ov-card-mrr">${money(sumB(arr))||"$0"} <span class="ov-card-u">MRR before</span></div>`+
      `<div class="ov-card-risk"><span class="ov-hi-dot"></span>${h.length.toLocaleString()} at risk · ${pct}% · ${money(sumB(h))||"$0"} MRR</div></div>`;
  };
  const closed = (stage,arr) => {
    const n=arr.length;
    return `<div class="${cls(stage)}" data-ovstage="${stage}" title="Click to focus the Overview on Closed${OVSTAGE===stage?" (click again to clear)":""}"><div class="ov-card-h">Closed</div>`+
      `<div class="ov-card-n">${n.toLocaleString()} <span class="ov-card-u">opps</span></div>`+
      `<div class="ov-card-mrr">${money(sumB(arr))||"$0"} <span class="ov-card-arw">→</span> ${money(sumA(arr))||"$0"}</div>`+
      `<div class="ov-card-risk ov-arch">risk archived</div></div>`;
  };
  return `<div class="ov-cards">${live("Open","open",g.open)}${live("Pending Fulfillment","pf",g.pf)}${closed("closed",g.closed)}</div>`;
}
// LEFT — Book insights column (grouped label/value rows). Computes over L (live=open+pf) unless noted.
function ovInsights(L,O){
  const n=L.length, nO=O.length;
  const cnt = (arr,f)=>arr.filter(f).length;
  const pct = (arr,f)=>arr.length?Math.round(100*cnt(arr,f)/arr.length):0;
  const mean = arr => { const a=arr.filter(x=>x!=null).map(x=>+x); return a.length? a.reduce((s,x)=>s+x,0)/a.length : null; };
  const grp = t => `<div class="ov-ins-grp">${t}</div>`;
  const row = (k,v,att) => `<div class="ov-ins-row"><span class="ov-ins-k">${k}</span><span class="ov-ins-v${att?" att":""}">${v}</span></div>`;
  // pct + count variant: % right-aligned in a fixed column, muted count trailing in its own sub-column
  const rowc = (k,pct,cntStr,att) => { const c=(cntStr||"").replace(/^·\s*/,"").trim();
    return `<div class="ov-ins-rowc"><div class="ov-ins-row"><span class="ov-ins-k">${k}</span><span class="ov-ins-v num-col${att?" att":""}">${pct}</span></div>${c?`<div class="ov-ins-cntrow">${c}</div>`:""}</div>`; };
  // OUTREACH
  const introN = cnt(L,r=>isY(r.intro_call));
  const connect = introN? Math.round(100*cnt(L,r=>isY(r.intro_call)&&isY(r.intro_connect))/introN) : 0;
  // CONTACT ≤21d: share of live opps we've reached on each channel within the gone-quiet threshold
  // (positive framing — the inverse of the 3 gone-quiet risk signals). Median age shown as muted context.
  const within21 = f => pct(L, r=>{ const d=daysSince(r[f]); return d!=null && d<=21; });
  const medAge = f => { const m=median(L.map(r=>daysSince(r[f]))); return m==null?"":`median ${m}d`; };
  // RECOMMENDATION & SLA
  const d2def = median(L.map(r=>r.days_to_rec_cycle));
  const trfd  = median(L.map(r=>r.days_to_default));
  const terc  = median(L.map(r=>r.time_in_erc));
  const meanAlt = mean(L.map(r=>r.alt_created));
  const d2alt = median(L.filter(r=>r.alt_published_date).map(r=> r.alt_published_days!=null?r.alt_published_days:r.days_to_alt ));
  // % outside SLA (na-excluded — same denominator as the Advising SLA dashboard: opps that reached the stage)
  const outSLA = (f,minE=1) => { const m=cnt(L,r=>r[f]==="Met"), x=cnt(L,r=>r[f]==="Missed"), e=m+x;
    return e>=minE? {pct:`${Math.round(100*x/e)}%`, cnt:`· ${x.toLocaleString()} of ${e.toLocaleString()}`, att:(100*x/e)>=40} : {pct:"—",cnt:"",att:false}; };
  const rfdO=outSLA("rfd_sla"), ercO=outSLA("erc_sla"), altO=outSLA("alt_sla"), tktO=outSLA("ticket_sla",5), emlO=outSLA("email_sla");
  // PREMIUM (medical)
  const medDelta = median(L.map(r=>r.rate_increase_pct));
  // FLAGS
  const lfBand = r => (r.lf_savings_band==="High"||r.lf_savings_band==="Medium"||r.lf_savings_band==="Low");
  const recertOpen = cnt(L,r=>r.recert_status && r.recert_status!=="Recert Approved");
  const packetNeeded = cnt(L,r=>/packet/i.test(r.blocked_reason||""));
  const borTerm = cnt(L,r=>isY(r.bor_term) || /Termination|BoR/i.test(r.blocked_reason||""));
  const col = inner => `<div class="ov-ins-col">${inner}</div>`;
  return `<div class="ov-panel ov-insights"><div class="ov-ins-h">Book insights</div>`+
    `<div class="ov-insstrip">`+
    col(
      grp("OUTREACH")+
      row("Intro complete", pct(L,r=>isY(r.intro_call))+"%")+
      row("Connect rate", connect+"%")+
      row("Email due (unanswered)", cnt(L,r=>isY(r.email_due)).toLocaleString(), true)+
      rowc("Email outside SLA", emlO.pct, emlO.cnt, emlO.att)+
      row("Outreach pending (no rec)", (nO?Math.round(100*cnt(O,r=>!r.default_rec_sent)/nO):0)+"%", true)
    )+
    col(
      grp("CONTACT &le;21d (share reached · median age)")+
      rowc("Emailed out", within21("last_outbound_email_date")+"%", medAge("last_outbound_email_date"))+
      rowc("Customer reply in", within21("last_inbound_email_date")+"%", medAge("last_inbound_email_date"))+
      rowc("Connected (call)", within21("last_connect_date")+"%", medAge("last_connect_date"))
    )+
    col(
      grp("RECOMMENDATION &amp; SLA")+
      row("Default rec sent", pct(L,r=>!!r.default_rec_sent)+"%")+
      row("Days to default (create→sent)", (d2def==null?"—":d2def+"d"))+
      row("Time in RFD", (trfd==null?"—":trfd+"d"))+
      row("Time in ERC", (terc==null?"—":terc+"d"))+
      rowc("RFD outside SLA", rfdO.pct, rfdO.cnt, rfdO.att)+
      rowc("ERC outside SLA", ercO.pct, ercO.cnt, ercO.att)+
      rowc("ALT outside SLA", altO.pct, altO.cnt, altO.att)+
      rowc("Ticket outside SLA", tktO.pct, tktO.cnt, tktO.att)+
      rowc("Alt requested", pct(L,r=>isY(r.alt_requested))+"%", `· ${cnt(L,r=>isY(r.alt_requested)).toLocaleString()} of ${L.length.toLocaleString()}`)+
      rowc("Alt published", pct(L,r=>!!r.alt_published_date)+"%", `· ${cnt(L,r=>!!r.alt_published_date).toLocaleString()} of ${L.length.toLocaleString()}`)+
      row("Avg alt packages", (meanAlt==null?"—":meanAlt.toFixed(2)))+
      row("Days to alt published", (d2alt==null?"—":d2alt+"d"))
    )+
    col(
      grp("PREMIUM (medical)")+
      row("Median Δ", (medDelta==null?"—":medDelta+"%"))+
      row("≥15%", pct(L,r=>r.rate_increase_pct!=null&&r.rate_increase_pct>=15)+"%", true)+
      row("≥20%", pct(L,r=>r.rate_increase_pct!=null&&r.rate_increase_pct>=20)+"%", true)
    )+
    col(
      grp("FLAGS")+
      row("LF available", pct(L,lfBand)+"%")+
      row("Auto-renewal", pct(L,r=>isY(r.auto_renewal))+"%")+
      row("Default automation", pct(L,r=>isY(r.default_automation))+"%")+
      row("Recert open", recertOpen.toLocaleString(), true)+
      row("Packet needed", packetNeeded.toLocaleString(), true)+
      row("BoR / Term", borTerm.toLocaleString(), true)
    )+
    `</div></div>`;
}
// RIGHT box 1 — Open: priority outreach + risk (bar = total scaled to max tier total; red overlay = High)
function ovRiskOpenTiers(O){
  const t={}; for(let p=1;p<=5;p++) t[p]={total:0,High:0};
  O.forEach(r=>{ const p=r.queue_tier; if(p==null||!t[p]) return;
    t[p].total++; if(riskCached(r).tier==="High") t[p].High++; });
  const maxTotal=Math.max(1, ...Object.keys(t).map(p=>t[p].total));
  const BARW=242, scale=v=>((v||0)/maxTotal)*BARW;
  let rows="";
  for(let p=1;p<=5;p++){
    const d=t[p], gw=scale(d.total), rw=scale(d.High);
    rows += `<div class="ov-qrow" data-ovtier="${p}" title="Open · P${p} — open the tab filtered to P${p}">`+
      `<div class="ov-qhead"><span class="ov-qlab">P${p} ${esc(OV_TIER_LABEL[p]||"")}</span><span class="ov-arw">→</span></div>`+
      `<div class="ov-pbar" style="width:${BARW}px">`+
        `<span class="g" style="width:${gw}px"></span>`+
        `<span class="ov-seg r" data-ovtier="${p}" data-ovrisk="high" style="width:${d.High>0?Math.max(rw,2):0}px" title="P${p} · High — filter to High risk"></span>`+
      `</div>`+
      `<div class="ov-qcnt">${d.total.toLocaleString()} opps · <b style="color:${OV_HI}">${d.High.toLocaleString()} High</b></div></div>`;
  }
  return `<div class="ov-panel"><div class="ov-panel-h">Open — priority outreach + risk</div>${rows}</div>`;
}
// generic ranked-factor bar box
function ovFactorBox(rowsData, title, tab, LABELMAP, topN){
  const max=Math.max(1, ...rowsData.map(e=>e[1]));
  const BARW=200;
  let list = rowsData.slice().sort((a,b)=>b[1]-a[1]);
  if (topN) list = list.slice(0, topN);
  const body = list.map(([k,c])=>{ const w=(c/max)*BARW, lab=LABELMAP[k]||k;
    return `<div class="ov-frow" data-ovtab="${tab}" data-ovrisk="high" title="${esc(lab)} — go to ${tab==="pf"?"PF":"Open"} tab, High risk">`+
      `<div class="ov-qhead"><span class="ov-qlab">${esc(lab)}</span><span class="ov-arw">→</span></div>`+
      `<span class="ov-fbar-track"><span class="ov-fbar" style="width:${w}px"></span></span><span class="ov-fcnt">${c.toLocaleString()}</span></div>`;
  }).join("");
  return `<div class="ov-panel"><div class="ov-panel-h">${title}</div>${body||`<div class="ov-qcnt" style="padding:6px">No firing factors in scope.</div>`}</div>`;
}
// RIGHT boxes 2 & 3 — risk H/M/L totals with a click-through "what's driving it" panel.
// boxKey: "open" | "pf" (also the drill tab). LABELMAP scopes which firing factors are listed.
function ovRiskTierBox(rowsData, title, boxKey, LABELMAP){
  const tiers=["High","Med","Low"], labOf={High:"High",Med:"Medium",Low:"Low"}, colOf={High:OV_HI,Med:OV_MED,Low:OV_LO};
  const byTier={High:[],Med:[],Low:[]};
  rowsData.forEach(r=>{ const t=riskCached(r).tier; (byTier[t]||byTier.Low).push(r); });
  const max=Math.max(1, byTier.High.length, byTier.Med.length, byTier.Low.length);
  const BARW=210, sel=OVRISK[boxKey];
  const bars = tiers.map(t=>{ const arr=byTier[t], w=(arr.length/max)*BARW, on=sel===t;
    return `<div class="ov-frow ov-risktier${on?" on":""}" data-ovrisktier="${t}" data-ovriskbox="${boxKey}" title="Click to see what's driving ${labOf[t]} risk">`+
      `<div class="ov-qhead"><span class="ov-qlab"><span class="ov-riskdot" style="background:${colOf[t]}"></span>${labOf[t]}</span><span class="ov-fcnt">${arr.length.toLocaleString()}</span></div>`+
      `<span class="ov-fbar-track"><span class="ov-fbar" style="width:${w}px;background:${colOf[t]}"></span></span></div>`;
  }).join("");
  let detail="";
  if (sel){
    const arr=byTier[sel], counts={};
    arr.forEach(r=>{ (riskCached(r).firing||[]).forEach(s=>{ if(LABELMAP[s.key]) counts[s.key]=(counts[s.key]||0)+1; }); });
    const data=Object.keys(counts).map(k=>[k,counts[k]]).sort((a,b)=>b[1]-a[1]);
    const dmax=Math.max(1, ...data.map(e=>e[1]));
    const rows = data.length ? data.map(([k,c])=>{ const w=(c/dmax)*170;
      return `<div class="ov-frow" data-ovtab="${boxKey}" data-ovrisktierfilter="${sel}" title="${esc(LABELMAP[k])} — open ${boxKey==="pf"?"PF":"Open"} tab, ${labOf[sel]} risk">`+
        `<div class="ov-qhead"><span class="ov-qlab">${esc(LABELMAP[k])}</span><span class="ov-arw">→</span></div>`+
        `<span class="ov-fbar-track"><span class="ov-fbar" style="width:${w}px"></span></span><span class="ov-fcnt">${c.toLocaleString()}</span></div>`;
    }).join("") : `<div class="ov-qcnt" style="padding:6px">No firing factors for ${labOf[sel]} risk in scope.</div>`;
    detail=`<div class="ov-riskdetail"><div class="ov-riskdetail-h">What's driving ${labOf[sel]} risk (${arr.length.toLocaleString()} opps)</div>${rows}</div>`;
  }
  return `<div class="ov-panel"><div class="ov-panel-h">${title}</div>${bars}${detail}</div>`;
}
function ovRollup(){
  if (OVSCOPE.mode==="ic") return "";
  const isTeam = OVSCOPE.mode==="team";
  let scopeRows = isTeam ? HUB : HUB.filter(r=>OVSCOPE.peSel.has(r.pe));
  if (OVSTAGE) scopeRows = scopeRows.filter(r=>tabOf(r)===OVSTAGE);
  const keyOf = isTeam ? (r=>r.pe) : (r=>r.advisor);
  const map=new Map();
  scopeRows.forEach(r=>{ const key=keyOf(r); if(!key) return;
    if(!map.has(key)) map.set(key,{name:key,live:0,openHigh:0,pfHigh:0,rfdM:0,rfdX:0,ercM:0,ercX:0,altM:0,altX:0,tktM:0,tktX:0,emlM:0,emlX:0});
    const o=map.get(key), t=tabOf(r);
    if(t==="open"||t==="pf") o.live++;
    if(t==="open" && riskCached(r).tier==="High") o.openHigh++;
    if(t==="pf"   && riskCached(r).tier==="High") o.pfHigh++;
    if(r.rfd_sla==="Met")o.rfdM++; else if(r.rfd_sla==="Missed")o.rfdX++;
    if(r.erc_sla==="Met")o.ercM++; else if(r.erc_sla==="Missed")o.ercX++;
    if(r.alt_sla==="Met")o.altM++; else if(r.alt_sla==="Missed")o.altX++;
    if(r.ticket_sla==="Met")o.tktM++; else if(r.ticket_sla==="Missed")o.tktX++;
    if(r.email_sla==="Met")o.emlM++; else if(r.email_sla==="Missed")o.emlX++;
  });
  const rows=[...map.values()].map(o=>({...o,total:o.openHigh+o.pfHigh})).sort((a,b)=>b.total-a.total);
  const max=Math.max(1, ...rows.map(o=>o.total));
  const attr = isTeam ? "data-ovpe" : "data-ovic";
  const colHead = isTeam ? "PE TEAM" : "IC";
  // compact single-cell SLA: RFD·ERC·ALT·TKT·EMAIL (miss %, na-excluded; "–" when no eligible)
  const seg=(m,x,minE=1)=>{ const e=m+x; if(e<minE) return `<span class="ov-s5-na" title="no eligible">–</span>`;
    const p=Math.round(100*x/e), c=p>=55?"#c0392b":(p>=40?"#b7791f":"var(--g6)");
    return `<span style="color:${c}${p>=40?";font-weight:700":""}" title="${x.toLocaleString()} of ${e.toLocaleString()} missed · na excluded">${p}</span>`; };
  const slaCell=o=>`<td class="ov-rsla5" title="Outside SLA % — RFD · ERC · ALT · Ticket · Email (na excluded)">`+
    seg(o.rfdM,o.rfdX)+`<i>·</i>`+seg(o.ercM,o.ercX)+`<i>·</i>`+seg(o.altM,o.altX)+`<i>·</i>`+seg(o.tktM,o.tktX,5)+`<i>·</i>`+seg(o.emlM,o.emlX)+`</td>`;
  const body=rows.map(o=>{ const w=(o.total/max)*150;
    return `<tr class="ov-rrow" ${attr}="${esc(o.name)}" title="${isTeam?"See this PE's roll-up":"See this IC's book"}">`+
      `<td class="ov-rname">${esc(o.name)}</td>`+
      `<td class="ov-rnum">${o.live.toLocaleString()}</td>`+
      `<td class="ov-rhi">${o.openHigh}</td>`+
      `<td class="ov-rhi">${o.pfHigh}</td>`+
      `<td class="ov-rtotcell"><span class="ov-rtot"><span class="ov-rtot-bar"><span style="width:${w}px"></span></span><b>${o.total}</b></span></td>`+
      slaCell(o)+`</tr>`;
  }).join("");
  return `<div class="ov-panel ov-rollup"><div class="ov-rscroll"><table class="ov-rtable">`+
    `<thead><tr><th>${colHead}</th><th>LIVE OPPS</th><th>OPEN HIGH</th><th>PF HIGH</th><th>AT-RISK TOTAL →</th>`+
    `<th class="ov-rsla-grp" title="Outside SLA miss % — na excluded">OUTSIDE SLA %<div class="ov-rsla-key">RFD·ERC·ALT·TKT·EM</div></th></tr></thead>`+
    `<tbody>${body||`<tr><td colspan="6" class="t-ok" style="padding:16px 14px">No rows in scope.</td></tr>`}</tbody></table></div></div>`;
}
function ovSeedScope(){
  const pes=ovPEs(), ics=ovICs(null);
  const peSet=new Set(pes), icSet=new Set(ics);
  // prune stale keys only. NOTE: do NOT auto-reseed to ALL when a scope set is
  // empty — toggling to "none" must keep an empty scope (menu stays open).
  [...OVSCOPE.peSel].forEach(k=>{ if(!peSet.has(k)) OVSCOPE.peSel.delete(k); });
  [...OVSCOPE.icSel].forEach(k=>{ if(!icSet.has(k)) OVSCOPE.icSel.delete(k); });
}
function ovScopeLabel(sel, total, noun){
  if (sel.size===0 || sel.size===total) return "All "+noun+"s";
  if (sel.size===1) return [...sel][0];
  return sel.size+" "+noun+"s";
}
// Body-only render — used when the scope selection or stage/risk toggles change,
// so the scope dropdown DOM (and its open menu) is NOT torn down mid-interaction.
function ovRenderBody(){
  const pes=ovPEs(), ics=ovICs(null);
  const allRows=ovRows(), gAll=ovStageSplit(allRows);   // stage cards always show full split
  const scoped = OVSTAGE ? allRows.filter(r=>tabOf(r)===OVSTAGE) : allRows;
  const g=ovStageSplit(scoped);
  const stageNote = OVSTAGE ? ` · focused on ${OVSTAGE==="pf"?"PF":OVSTAGE.charAt(0).toUpperCase()+OVSTAGE.slice(1)}` : "";
  let title, sub;
  if (OVSCOPE.mode==="team"){
    title="Overview · Team-wide · risk by PE team";
    sub=`All PE teams · ${allRows.length.toLocaleString()} renewals${stageNote} · click a PE → their roll-up (then drill to an IC)`;
  } else if (OVSCOPE.mode==="pe"){
    title=`Overview · PE — ${esc(ovScopeLabel(OVSCOPE.peSel,pes.length,"PE"))} · risk across ICs`;
    sub=`${allRows.length.toLocaleString()} renewals${stageNote} · Open ${gAll.open.length} · PF ${gAll.pf.length} · Closed ${gAll.closed.length} · click an IC → their book`;
  } else {
    title=`Overview · IC — ${esc(ovScopeLabel(OVSCOPE.icSel,ics.length,"IC"))}`;
    sub=`Their book only · ${allRows.length.toLocaleString()} renewals${stageNote} · Open ${gAll.open.length} · PF ${gAll.pf.length} · Closed ${gAll.closed.length}`;
  }
  const O=g.open, P=g.pf, L=O.concat(P);
  const insstrip=ovInsights(L,O);
  const threebox=`<div class="ov-3box">${ovRiskOpenTiers(O)}${ovRiskTierBox(O,"Open — risk","open",OV_OPEN_FACTOR_LABEL)}${ovRiskTierBox(P,"PF — risk","pf",OV_PF_FACTOR_LABEL)}</div>`;
  el("ovBody").innerHTML =
    `<div class="ov-title">${title}</div><div class="ov-sub">${sub}</div>`+
    ovStageCards(gAll)+insstrip+threebox+ovRollup();
}
function renderOverview(){
  ovSeedScope();
  const pes=ovPEs(), ics=ovICs(null);
  el("ovScope").innerHTML = ovScopeBar();
  // scope-chip wiring (rebuilt with the scope bar); switching mode seeds that mode's set to ALL
  el("ovScope").querySelectorAll(".ov-chip").forEach(b=>b.addEventListener("click",()=>{
    const m=b.dataset.ovmode; OVSCOPE.mode=m;
    if (m==="pe") ovPEs().forEach(p=>OVSCOPE.peSel.add(p));
    if (m==="ic") ovICs(null).forEach(a=>OVSCOPE.icSel.add(a));
    renderOverview();
  }));
  // scope multi-select drops — onChange updates the BODY only (keeps the menu open on toggle-to-none)
  if (OVSCOPE.mode==="pe" && el("ovPeDrop"))
    multiDrop("ovPeDrop","PE(s)",pes.map(p=>({key:p,label:p})),OVSCOPE.peSel,ovRenderBody);
  if (OVSCOPE.mode==="ic" && el("ovIcDrop"))
    multiDrop("ovIcDrop","IC(s)",ics.map(a=>({key:a,label:a})),OVSCOPE.icSel,ovRenderBody);
  ovRenderBody();
}
function ovDrill(opts){
  opts = opts||{};
  const tab = opts.tab, tier = opts.tier, risk = opts.risk, riskTier = opts.riskTier;
  // apply current scope to the grid filters
  if (OVSCOPE.mode==="pe" && OVSCOPE.peSel.size){ SEL.pe.clear(); OVSCOPE.peSel.forEach(k=>SEL.pe.add(k)); }
  else if (OVSCOPE.mode==="ic" && OVSCOPE.icSel.size){ SEL.adv.clear(); OVSCOPE.icSel.forEach(k=>SEL.adv.add(k)); }
  // team: leave adv/pe as-is
  if (tier!=null){ SEL.tier.clear(); SEL.tier.add(String(tier)); }
  else { SEL.tier.clear(); ((DROPS.tier&&DROPS.tier.items)||[]).forEach(i=>SEL.tier.add(i.key)); }
  if (riskTier){ SEL.risk.clear(); SEL.risk.add(riskTier); }          // "High" | "Med" | "Low"
  else if (risk==="high"){ SEL.risk.clear(); SEL.risk.add("High"); }
  else { SEL.risk.clear(); ["High","Med","Low"].forEach(k=>SEL.risk.add(k)); }
  Object.keys(DROPS).forEach(k=>{ const d=DROPS[k]; if(d&&d.sync) d.sync(); });
  showTab(tab);
}
// delegated clicks on the Overview body (bound once — the element persists)
el("ovBody").addEventListener("click", e => {
  // stage-tile filter toggle (null=all · click again clears)
  const sc=e.target.closest("[data-ovstage]");
  if(sc){ const s=sc.dataset.ovstage; OVSTAGE = (OVSTAGE===s)?null:s; ovRenderBody(); return; }
  // risk H/M/L tier bar → expand/collapse the "what's driving it" panel in-pane
  const rt=e.target.closest("[data-ovrisktier]");
  if(rt){ const box=rt.dataset.ovriskbox, t=rt.dataset.ovrisktier;
    OVRISK[box] = (OVRISK[box]===t)?null:t; ovRenderBody(); return; }
  const seg=e.target.closest(".ov-seg[data-ovrisk]");
  if(seg){ ovDrill({tab:"open", tier:+seg.dataset.ovtier, risk:seg.dataset.ovrisk}); return; }
  const q=e.target.closest("[data-ovtier]");
  if(q){ ovDrill({tab:"open", tier:+q.dataset.ovtier}); return; }
  const f=e.target.closest("[data-ovtab]");
  if(f){ ovDrill({tab:f.dataset.ovtab, risk:f.dataset.ovrisk||undefined,
                  riskTier:f.dataset.ovrisktierfilter||undefined,
                  tier:(f.dataset.ovtier!=null&&f.dataset.ovtier!=="")?+f.dataset.ovtier:undefined}); return; }
  const pe=e.target.closest("[data-ovpe]");
  if(pe){ OVSCOPE.mode="pe"; OVSCOPE.peSel.clear(); OVSCOPE.peSel.add(pe.getAttribute("data-ovpe")); renderOverview(); return; }
  const ic=e.target.closest("[data-ovic]");
  if(ic){ OVSCOPE.mode="ic"; OVSCOPE.icSel.clear(); OVSCOPE.icSel.add(ic.getAttribute("data-ovic")); renderOverview(); return; }
});

/* ============================================================ tabs */
function showTab(name){
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.pane===name));
  if (name==="guide"){
    el("pane-table").classList.remove("on");
    el("pane-script").classList.remove("on");
    el("pane-overview").classList.remove("on");
    el("pane-guide").classList.add("on");
    window.scrollTo({top:0, behavior:"smooth"});
    return;
  }
  if (name==="overview"){
    el("pane-table").classList.remove("on");
    el("pane-script").classList.remove("on");
    el("pane-guide").classList.remove("on");
    el("pane-overview").classList.add("on");
    renderOverview();
    window.scrollTo({top:0, behavior:"smooth"});
    return;
  }
  if (name==="script"){
    el("pane-table").classList.remove("on");
    el("pane-overview").classList.remove("on");
    el("pane-guide").classList.remove("on");
    el("pane-script").classList.add("on");
    renderScript();
    window.scrollTo({top:0, behavior:"smooth"});
    return;
  }
  el("pane-script").classList.remove("on");
  el("pane-overview").classList.remove("on");
  el("pane-guide").classList.remove("on");
  el("pane-table").classList.add("on");
  LAST_TABLE_TAB = name;
  TAB = name; CLOSED = (name==="closed"); OPEN=null; PAGE=1;
  if (name==="closed" && (SORT.k==="tier")) SORT={k:"closedon",dir:-1};
  if (name!=="closed" && (SORT.k==="closedon")) SORT={k:"tier",dir:1};
  persist();
  render();
}
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => showTab(t.dataset.pane)));
el("bBackTable").addEventListener("click", () => showTab(LAST_TABLE_TAB));
el("bGeneric").addEventListener("click", () => { SCRIPT_ROW = null; renderScript(); });
el("tSample").addEventListener("change", () => el("scriptDoc").classList.toggle("sampleonly", el("tSample").checked));

/* ============================================================ wiring + init */
el("fSearch").addEventListener("input", () => { OPEN=null; PAGE=1; persist(); render(); });
(function(){
  const top = el("tblTop"), wrap = el("tblwrap");
  if (!top || !wrap) return;
  let lock = false;
  top.addEventListener("scroll", () => { if (lock) return; lock = true; wrap.scrollLeft = top.scrollLeft; lock = false; });
  wrap.addEventListener("scroll", () => { if (lock) return; lock = true; top.scrollLeft = wrap.scrollLeft; lock = false; });
  window.addEventListener("resize", syncTopScroll);
})();
el("body").addEventListener("click", e => {
  const sb = e.target.closest && e.target.closest("[data-script]");
  if (sb){ e.stopPropagation(); openScript(sb.dataset.script); return; }
  const th = e.target.closest && e.target.closest("table.lines th[data-sk]");
  if (th){ e.stopPropagation(); const sk=th.dataset.sk;
    DRILL_SORT = (DRILL_SORT.k===sk)?{k:sk,dir:-DRILL_SORT.dir}:{k:sk,dir:-1}; render(); }
}, true);

buildFilters();
buildScriptSearch();
restoreState();
// reflect restored selections in the dropdown UIs
Object.keys(DROPS).forEach(k => { const d=DROPS[k]; if (d && d.sync) d.sync(); });
// reflect the restored active data tab in the tab bar
document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.pane===TAB));
render();
showTab("overview");   // Overview is the default landing tab
</script>
</body>
</html>
"""

html = TEMPLATE.replace("__GUIDEHTML__", guide_html).replace("__HUBDATA__", data_json)
open(OUT, "w").write(html)
print(f"wrote {OUT}  ({len(html)/1024:.0f} KB)  opps={n_opps} lines={n_lines}")
