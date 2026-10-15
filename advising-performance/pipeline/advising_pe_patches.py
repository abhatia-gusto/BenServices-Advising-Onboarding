#!/usr/bin/env python3
"""Durable, idempotent re-applier for the Advising Performance PE-view customizations.

Unlike NPR (gen8.py) and Broker (template), the Advising dashboard HTML is self-modified
in place by inject_v11_core_data.py — there is no from-scratch generator. These three JS
customizations therefore live only in advising_performance_dashboard_v11.html:

  1. poolTeam() + pooled PE summary  — PE Avg Weighted / QPR are the team's pooled book
     (sum raw met/total across active ICs → calcAttainment), not an average of IC %s.
  2. Broker-style blended drill        — the PE expand is a per-metric IC table sorted by
     QPR desc with a TEAM BLENDED pooled row at the bottom.
  3. autoSelectICs() off-list fix      — the default IC selection honors DEFAULT_OFF so the
     new-hire/transfer off-list actually renders unchecked (was being re-checked on init).

Each transform is idempotent: if the customization is already present it is skipped; if the
HTML is the original (pre-customization) baseline it is applied. So a normal refresh re-runs
this as a no-op, and a reverted/rebuilt HTML is repaired. Run after the inject_* steps, before
publishing. Safe to run standalone:  python3 advising_pe_patches.py [path-to-v11-html]
"""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT = HERE / "advising_performance_dashboard_v11.html"

POOLTEAM = (
"function poolTeam(team){\n"
"  var ms=Array.from(sMonths),r={};\n"
"  function agg(field){var m=0,t=0;team.forEach(function(a){ms.forEach(function(mo){if(a[field]&&a[field][mo]){m+=a[field][mo].met;t+=a[field][mo].total}})});return t>0?pc(m,t):null;}\n"
"  r.erConfirm=agg('erConfirm');r.rfd=agg('rfd');r.tixSla=agg('tixSla');\n"
"  var trX=0,trO=0;team.forEach(function(a){ms.forEach(function(mo){if(a.tixRate&&a.tixRate[mo]){trX+=a.tixRate[mo].tix;trO+=a.tixRate[mo].orders}})});r.tixRate=trO>0?pc(trX,trO):null;\n"
"  var qS=0,qC=0;team.forEach(function(a){ms.forEach(function(mo){if(a.quality&&a.quality[mo]){qS+=a.quality[mo].sum;qC+=a.quality[mo].count}})});r.quality=qC>0?Math.round(qS/qC*10)/10:null;\n"
"  var avEl=0,avM=0;team.forEach(function(a){var av=D.availData[a.name]||{};ms.forEach(function(mo){if(av[mo]){avEl+=av[mo].eligible||0;avM+=av[mo].met||0}})});r.availability=avEl>0?Math.round(avM/avEl*1000)/10:null;\n"
"  var abIn=0,abAb=0;team.forEach(function(a){var ab=D.abandonData[a.name]||{};ms.forEach(function(mo){if(ab[mo]){abIn+=ab[mo].inbound||0;abAb+=ab[mo].abandonedMod||0}})});r.abandon=abIn>0?Math.round(abAb/abIn*10000)/100:null;\n"
"  return r;\n"
"}\n"
)

AVG_OLD = (
"    var avgW = team.reduce(function(s,r){return s + r.att.avgWeighted}, 0) / n;\n"
"    var avgQ = team.reduce(function(s,r){return s + (r.att.qpr != null ? r.att.qpr : 0)}, 0) / n;"
)
AVG_NEW = (
"    var _patt = calcAttainment(poolTeam(team));  // cumulative pooled roll-up (not avg-of-avgs)\n"
"    var avgW = _patt.avgWeighted!=null?_patt.avgWeighted:0;\n"
"    var avgQ = _patt.qpr!=null?_patt.qpr:0;"
)

SORT_OLD = "var va=a.att.avgWeighted, vb=b.att.avgWeighted;"
SORT_NEW = "var va=a.att.qpr, vb=b.att.qpr;"

AUTOSEL_OLD = "function autoSelectICs(){sA=new Set(ALL_ADVISORS);D.advisors.forEach(function(a){if(calcAttainment(cmAll(a)).avgWeighted==null)sA.delete(a.name);});}"
AUTOSEL_NEW = "function autoSelectICs(){sA=new Set(ALL_ADVISORS.filter(function(n){return !DEFAULT_OFF.has(n)}));D.advisors.forEach(function(a){if(calcAttainment(cmAll(a)).avgWeighted==null)sA.delete(a.name);});}"

DRILL_START = "var drill = \"<div class='pe-drill'><table class='pe-drill-tbl'>\";"
DRILL_END = "drill += \"</tbody></table></div>\";"
DRILL_NEW = r'''var MET=[["erConfirm","ER Confirm"],["rfd","RFD+Alt"],["tixSla","Ticket SLA"],["availability","Phone Avail."],["abandon","Abandon"],["tixRate","Ticket Rate"],["quality","LAI QA"]];
    function mcell(k,v,bold){
      if(v==null) return "<td class='r'>&mdash;</td>";
      var st=metricStatus(k,v);
      var bg=st==='goal'?'#E1F5EE':st==='floor'?'#FAEEDA':'#FCEBEB';
      var fg=st==='goal'?'#0F6E56':st==='floor'?'#854F0B':'#A32D2D';
      var disp=(k==='quality')?v.toFixed(0):v.toFixed(0)+'%';
      return "<td class='r'><span style='background:"+bg+";color:"+fg+";padding:2px 8px;border-radius:10px;"+(bold?'font-weight:600;':'')+"'>"+disp+"</span></td>";
    }
    var drill = "<div class='pe-drill'><table class='pe-drill-tbl'>";
    drill += "<thead><tr><th>Advisor</th>";
    MET.forEach(function(m){ drill += "<th class='r'>"+m[1]+"</th>"; });
    drill += "<th class='r'>WTD</th><th class='r'>QPR</th></tr></thead><tbody>";
    if(team.length===0){
      drill += "<tr><td colspan='"+(MET.length+3)+"' class='pe-drill-empty'>No advisors on this team match the current filters.</td></tr>";
    } else {
      team.forEach(function(r){
        drill += "<tr><td class='nm icnm' data-icname='"+escAttr(r.name)+"' title='Click to view report'>"+escHtml(r.name)+"</td>";
        MET.forEach(function(m){ drill += mcell(m[0], r.metrics[m[0]], false); });
        var aW=r.att.avgWeighted, qV=r.att.qpr;
        drill += "<td class='r' style='font-weight:600;color:"+(aW==null?'var(--gt)':colAvg(aW))+"'>"+(aW==null?'&mdash;':aW.toFixed(1))+"</td>";
        drill += "<td class='r' style='font-weight:600;color:"+(qV==null?'var(--gt)':colQpr(qV))+"'>"+(qV==null?'&mdash;':qV.toFixed(1))+"</td></tr>";
      });
      var bm=poolTeam(team), batt=calcAttainment(bm);
      drill += "<tr style='border-top:2px solid #cfcfcf'><td class='nm' style='font-weight:600'>TEAM BLENDED <span class='sub'>"+team.length+" IC"+(team.length===1?"":"s")+"</span></td>";
      MET.forEach(function(m){ drill += mcell(m[0], bm[m[0]], true); });
      drill += "<td class='r' style='font-weight:700;color:"+(batt.avgWeighted==null?'var(--gt)':colAvg(batt.avgWeighted))+"'>"+(batt.avgWeighted==null?'&mdash;':batt.avgWeighted.toFixed(1))+"</td>";
      drill += "<td class='r' style='font-weight:700;color:"+(batt.qpr==null?'var(--gt)':colQpr(batt.qpr))+"'>"+(batt.qpr==null?'&mdash;':batt.qpr.toFixed(1))+"</td></tr>";
    }
    drill += "</tbody></table></div>";'''


def apply(html):
    applied = []
    # 1. poolTeam()
    if "function poolTeam(team){" not in html:
        anchor = "function renderPE(rows){"
        if anchor in html:
            html = html.replace(anchor, POOLTEAM + anchor, 1)
            applied.append("poolTeam")
    # 2. pooled PE summary
    if "calcAttainment(poolTeam(team))" not in html and AVG_OLD in html:
        html = html.replace(AVG_OLD, AVG_NEW, 1)
        applied.append("pooled-PE")
    # 3. drill sort by QPR
    if SORT_OLD in html:
        html = html.replace(SORT_OLD, SORT_NEW, 1)
        applied.append("sort-by-qpr")
    # 4. autoSelectICs off-list fix
    if AUTOSEL_OLD in html:
        html = html.replace(AUTOSEL_OLD, AUTOSEL_NEW, 1)
        applied.append("autoSelectICs-offlist")
    # 5. blended drill
    if "TEAM BLENDED" not in html:
        i = html.find(DRILL_START)
        j = html.find(DRILL_END, i) if i >= 0 else -1
        if i >= 0 and j >= 0:
            html = html[:i] + DRILL_NEW + html[j + len(DRILL_END):]
            applied.append("blended-drill")
    return html, applied


REQUIRED_MARKERS = {
    "function poolTeam(team){": "pooled PE helper",
    "calcAttainment(poolTeam(team))": "pooled PE summary",
    "TEAM BLENDED": "blended drill row",
    "!DEFAULT_OFF.has(n)": "autoSelectICs off-list fix",
}


def verify(html):
    return [why for m, why in REQUIRED_MARKERS.items() if m not in html]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    html = path.read_text(encoding="utf-8")
    html, applied = apply(html)
    path.write_text(html, encoding="utf-8")
    missing = verify(html)
    print("advising_pe_patches: applied " + (", ".join(applied) if applied else "nothing (already current)"))
    if missing:
        sys.exit("ERROR: Advising PE customizations still missing after patch: " + ", ".join(missing))
    print("verify OK: pooled PE + blended drill + off-list fix all present")


if __name__ == "__main__":
    main()
