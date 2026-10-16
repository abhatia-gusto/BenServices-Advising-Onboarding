#!/usr/bin/env python3
"""Durable, idempotent re-applier for the Advising Performance PE view.

Advising's HTML is self-modified in place by inject_v11_core_data.py (no from-scratch
generator), so the PE-view customizations live only in advising_performance_dashboard_v11.html.
This module re-applies them on every refresh (no-op when present; full restore from the
pre-customization baseline if the HTML is ever reverted):

  1. HELPERS   — poolTeam()/rawFor()/dScore()/dEmail() globals (pooled roll-up + tracking + diag).
  2. autoSelectICs off-list fix — default selection honors DEFAULT_OFF (new-hire off-list).
  3. renderPE  — the PE view is one sortable table: a pooled PE row per team (all metrics +
     WTD/QPR + diagnostics) that expands to the team's ICs across the same columns; every
     column is sortable (default QPR desc).

Run after the inject_* steps, before publishing.  Standalone: python3 advising_pe_patches.py [html]
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT = HERE / "advising_performance_dashboard_v11.html"

HELPERS = r'''function poolTeam(team){
  var ms=Array.from(sMonths),r={};
  function agg(field){var m=0,t=0;team.forEach(function(a){ms.forEach(function(mo){if(a[field]&&a[field][mo]){m+=a[field][mo].met;t+=a[field][mo].total}})});return t>0?pc(m,t):null;}
  r.erConfirm=agg('erConfirm');r.rfd=agg('rfd');r.tixSla=agg('tixSla');
  var trX=0,trO=0;team.forEach(function(a){ms.forEach(function(mo){if(a.tixRate&&a.tixRate[mo]){trX+=a.tixRate[mo].tix;trO+=a.tixRate[mo].orders}})});r.tixRate=trO>0?pc(trX,trO):null;
  var qS=0,qC=0;team.forEach(function(a){ms.forEach(function(mo){if(a.quality&&a.quality[mo]){qS+=a.quality[mo].sum;qC+=a.quality[mo].count}})});r.quality=qC>0?Math.round(qS/qC*10)/10:null;
  var avEl=0,avM=0;team.forEach(function(a){var av=D.availData[a.name]||{};ms.forEach(function(mo){if(av[mo]){avEl+=av[mo].eligible||0;avM+=av[mo].met||0}})});r.availability=avEl>0?Math.round(avM/avEl*1000)/10:null;
  var abIn=0,abAb=0;team.forEach(function(a){var ab=D.abandonData[a.name]||{};ms.forEach(function(mo){if(ab[mo]){abIn+=ab[mo].inbound||0;abAb+=ab[mo].abandonedMod||0}})});r.abandon=abIn>0?Math.round(abAb/abIn*10000)/100:null;
  return r;
}
function rawFor(list,k){
  var ms=Array.from(sMonths), n=0, d=0;
  if(k==='quality'){ list.forEach(function(a){ms.forEach(function(mo){var x=a.quality&&a.quality[mo];if(x)d+=x.count;});}); return d?('n='+d):''; }
  if(k==='tixRate'){ list.forEach(function(a){ms.forEach(function(mo){var x=a.tixRate&&a.tixRate[mo];if(x){n+=x.tix;d+=x.orders;}});}); return d?(n+'/'+d):''; }
  if(k==='availability'){ list.forEach(function(a){var av=D.availData[a.name]||{};ms.forEach(function(mo){if(av[mo]){n+=av[mo].met||0;d+=av[mo].eligible||0;}});}); return d?(n+'/'+d):''; }
  if(k==='abandon'){ list.forEach(function(a){var ab=D.abandonData[a.name]||{};ms.forEach(function(mo){if(ab[mo]){n+=ab[mo].abandonedMod||0;d+=ab[mo].inbound||0;}});}); return d?(n+'/'+d):''; }
  list.forEach(function(a){ms.forEach(function(mo){var x=a[k]&&a[k][mo];if(x){n+=x.met;d+=x.total;}});}); return d?(n+'/'+d):'';
}
function dScore(sc,n,bg){bg=bg?('background:'+bg+';'):'';return sc==null?"<td class='r' style='"+bg+"'>&mdash;</td>":"<td class='r' style='padding:6px 9px;"+bg+"'><span style='color:"+colDiagScore(sc)+"'>"+sc.toFixed(2)+"</span><div style='font-size:10px;color:var(--gt)'>n="+n+"</div></td>";}
function dEmail(p,met,total,bg){bg=bg?('background:'+bg+';'):'';return p==null?"<td class='r' style='"+bg+"'>&mdash;</td>":"<td class='r' style='padding:6px 9px;"+bg+"'><span style='color:"+colDiagEmail(p)+"'>"+p.toFixed(0)+"%</span><div style='font-size:10px;color:var(--gt)'>"+met+"/"+total+"</div></td>";}
'''

RENDERPE = r'''function renderPE(rows){
  var sumEl=document.getElementById("peSummary"), tblEl=document.getElementById("peTable");
  if(!sumEl||!tblEl) return;
  if(!rows.length){ sumEl.innerHTML=""; tblEl.innerHTML="<div style='padding:40px;text-align:center;color:var(--gt)'>No advisors match filters</div>"; return; }
  var byPe={}; rows.forEach(function(r){ if(r.att.avgWeighted==null) return; var pe=r.pe||"(no PE)"; (byPe[pe]=byPe[pe]||[]).push(r); });
  var MET=[["erConfirm","ER Confirm"],["rfd","RFD+Alt"],["tixSla","Ticket SLA"],["availability","Phone Avail."],["abandon","Abandon"],["tixRate","Ticket Rate"],["quality","LAI QA"]];
  function escHtml(x){return String(x==null?"":x).replace(/[&<>\"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];});}
  function escAttr(x){return escHtml(x);}
  var BG_MET="#EFF5F4",BG_RATE="#FAF5EA",BG_DIAG="#F3F0F8";
  function mcell(kk,v,raw,bold,bg){bg=bg||'transparent';
    if(v==null) return "<td class='r' style='background:"+bg+"'>&mdash;</td>";
    var st=metricStatus(kk,v);
    var bg=st==='goal'?'#E1F5EE':st==='floor'?'#FAEEDA':'#FCEBEB';
    var fg=st==='goal'?'#0F6E56':st==='floor'?'#854F0B':'#A32D2D';
    var disp=(kk==='quality')?v.toFixed(0):v.toFixed(0)+'%';
    return "<td class='r' style='padding:6px 9px;white-space:nowrap;background:"+bg+"'><span style='background:"+bg+";color:"+fg+";padding:2px 8px;border-radius:10px;"+(bold?'font-weight:600;':'')+"'>"+disp+"</span>"+(raw?"<div style='font-size:10px;color:var(--gt);margin-top:2px'>"+raw+"</div>":"")+"</td>";
  }
  var peData=Object.keys(byPe).map(function(pe){
    var team=byPe[pe], pm=poolTeam(team), att=calcAttainment(pm);
    var r3=team.filter(function(r){return r.rating===3}).length, r2=team.filter(function(r){return r.rating===2}).length, r1=team.filter(function(r){return r.rating===1}).length;
    var cs=0,csn=0,ia=0,ian=0,em=0,et=0;
    team.forEach(function(r){var a=diagCsat(r.name);if(a.score!=null){cs+=a.score*a.n;csn+=a.n;}var b=diagInapp(r.name);if(b.score!=null){ia+=b.score*b.n;ian+=b.n;}var e=diagEmail(r.name);em+=e.met;et+=e.total;});
    return {pe:pe,team:team,n:team.length,pm:pm,att:att,r3:r3,r2:r2,r1:r1,csat:csn?cs/csn:null,csatN:csn,inapp:ian?ia/ian:null,inappN:ian,emailPct:et?em/et*100:null,emailMet:em,emailTot:et};
  });
  var totalIcs=peData.reduce(function(s,p){return s+p.n},0);
  var tR3=peData.reduce(function(s,p){return s+p.r3},0),tR2=peData.reduce(function(s,p){return s+p.r2},0),tR1=peData.reduce(function(s,p){return s+p.r1},0);
  var mW=totalIcs?peData.reduce(function(s,p){return s+(p.att.avgWeighted||0)*p.n},0)/totalIcs:null;
  var mQ=totalIcs?peData.reduce(function(s,p){return s+(p.att.qpr||0)*p.n},0)/totalIcs:null;
  function cA(v){return v==null?"var(--gt)":(v>=100?"var(--gn)":v>=85?"var(--teal)":v>=62.5?"var(--am)":"var(--rd)")} function cQ(v){return v==null?"var(--gt)":(v<=62.5?"var(--rd)":v>=100?"var(--gn)":v>=85?"var(--teal)":"var(--am)")}
  sumEl.innerHTML=
    "<div class='pe-stat'><div class='lbl'>Mean Avg Weighted</div><div class='val' style='color:"+cA(mW)+"'>"+(mW!=null?mW.toFixed(1)+"%":"&mdash;")+"</div><div class='sub'>weighted by team size</div></div>"+
    "<div class='pe-stat'><div class='lbl'>Mean QPR</div><div class='val' style='color:"+cQ(mQ)+"'>"+(mQ!=null?mQ.toFixed(1)+"%":"&mdash;")+"</div><div class='sub'>weighted by team size</div></div>"+
    "<div class='pe-stat'><div class='lbl'>Rating 3</div><div class='val' style='color:var(--gn)'>"+tR3+" / "+totalIcs+"</div><div class='sub'>"+(totalIcs?Math.round(tR3/totalIcs*100):0)+"%</div></div>"+
    "<div class='pe-stat'><div class='lbl'>Rating 2</div><div class='val' style='color:var(--am)'>"+tR2+" / "+totalIcs+"</div><div class='sub'>"+(totalIcs?Math.round(tR2/totalIcs*100):0)+"%</div></div>"+
    "<div class='pe-stat'><div class='lbl'>Rating 1</div><div class='val' style='color:var(--rd)'>"+tR1+" / "+totalIcs+"</div><div class='sub'>"+(totalIcs?Math.round(tR1/totalIcs*100):0)+"%</div></div>";
  if(typeof window.__peSortK==="undefined"){window.__peSortK="qpr";window.__peSortDir=-1;}
  function pval(p,key){ if(key==="pe")return p.pe.toLowerCase(); if(key==="wtd")return p.att.avgWeighted; if(key==="qpr")return p.att.qpr; if(key==="csat")return p.csat; if(key==="inapp")return p.inapp; if(key==="email")return p.emailPct; return p.pm[key]; }
  var COLS=[{k:"pe",l:"People Empowerer",a:"left",g:""}].concat(MET.map(function(m){return {k:m[0],l:m[1],a:"right",g:"met"};})).concat([{k:"wtd",l:"WTD",a:"right",g:"rate"},{k:"qpr",l:"QPR",a:"right",g:"rate"},{k:"csat",l:"CSAT",a:"right",g:"diag"},{k:"inapp",l:"In-App",a:"right",g:"diag"},{k:"email",l:"Email SLA",a:"right",g:"diag"}]);function gbg(g){return g==="met"?"#EFF5F4":g==="rate"?"#FAF5EA":g==="diag"?"#F3F0F8":"transparent";}
  function paint(){
    peData.sort(function(a,b){ var x=pval(a,window.__peSortK), y=pval(b,window.__peSortK);
      if(window.__peSortK==="pe"){return x<y?-window.__peSortDir:x>y?window.__peSortDir:0;}
      if(x==null)return 1; if(y==null)return -1; return (x-y)*window.__peSortDir; });
    var h="<div style='overflow-x:auto'><table class='pe-tbl' style='border-collapse:separate;border-spacing:0;width:100%;min-width:1040px;font-size:12px'><thead><tr>";
    COLS.forEach(function(c){ var ar=c.k===window.__peSortK?(window.__peSortDir<0?" ▾":" ▴"):""; h+="<th data-sk='"+c.k+"' style='text-align:"+c.a+";padding:8px 9px;color:var(--gt);font-weight:500;border-bottom:1px solid var(--gb);cursor:pointer;white-space:nowrap;background:"+gbg(c.g)+"'>"+c.l+ar+"</th>"; });
    h+="</tr></thead><tbody>";
    peData.forEach(function(p,idx){
      h+="<tr class='pe-main' data-pe='"+idx+"' style='cursor:pointer;background:var(--gl)'>";
      h+="<td style='padding:8px 9px;border-bottom:1px solid var(--gb);white-space:nowrap;font-weight:600'><span class='pe-caret' data-c='"+idx+"'>&#9656;</span> "+escHtml(p.pe)+" <span class='sub' style='font-weight:400'>"+p.n+" IC"+(p.n===1?"":"s")+" &middot; <b style='color:var(--gn)'>"+p.r3+"</b>&middot;<b style='color:var(--am)'>"+p.r2+"</b>&middot;<b style='color:var(--rd)'>"+p.r1+"</b></span></td>";
      MET.forEach(function(m){ h+=mcell(m[0],p.pm[m[0]],rawFor(p.team,m[0]),true,BG_MET); });
      h+="<td class='r' style='padding:6px 9px;font-weight:700;background:#FAF5EA;color:"+cA(p.att.avgWeighted)+"'>"+(p.att.avgWeighted==null?"&mdash;":p.att.avgWeighted.toFixed(1))+"</td>";
      h+="<td class='r' style='padding:6px 9px;font-weight:700;background:#FAF5EA;color:"+cQ(p.att.qpr)+"'>"+(p.att.qpr==null?"&mdash;":p.att.qpr.toFixed(1))+"</td>";
      h+=dScore(p.csat,p.csatN,BG_DIAG)+dScore(p.inapp,p.inappN,BG_DIAG)+dEmail(p.emailPct,p.emailMet,p.emailTot,BG_DIAG);
      h+="</tr>";
      p.team.slice().sort(function(a,b){var va=a.att.qpr,vb=b.att.qpr; if(va==null&&vb==null)return 0; if(va==null)return 1; if(vb==null)return -1; return vb-va;}).forEach(function(r){
        h+="<tr class='pe-ic' data-ic-of='"+idx+"' style='display:none;background:var(--wg)'>";
        h+="<td class='nm icnm' data-icname='"+escAttr(r.name)+"' title='Click to view report' style='padding:6px 9px 6px 32px;border-bottom:1px solid var(--gb);white-space:nowrap;cursor:pointer'>"+escHtml(r.name)+"</td>";
        MET.forEach(function(m){ h+=mcell(m[0],r.metrics[m[0]],rawFor([r],m[0]),false,BG_MET); });
        var aW=r.att.avgWeighted,qV=r.att.qpr;
        h+="<td class='r' style='padding:6px 9px;background:#FAF5EA;color:"+cA(aW)+"'>"+(aW==null?"&mdash;":aW.toFixed(1))+"</td>";
        h+="<td class='r' style='padding:6px 9px;background:#FAF5EA;color:"+cQ(qV)+"'>"+(qV==null?"&mdash;":qV.toFixed(1))+"</td>";
        var dc=diagCsat(r.name),di=diagInapp(r.name),de=diagEmail(r.name);
        h+=dScore(dc.score,dc.n,BG_DIAG)+dScore(di.score,di.n,BG_DIAG)+dEmail(de.pct,de.met,de.total,BG_DIAG);
        h+="</tr>";
      });
    });
    h+="</tbody></table></div>";
    tblEl.innerHTML=h;
    tblEl.querySelectorAll("th[data-sk]").forEach(function(th){ th.addEventListener("click",function(){ var key=th.getAttribute("data-sk"); if(key===window.__peSortK)window.__peSortDir=-window.__peSortDir; else {window.__peSortK=key;window.__peSortDir=(key==="pe"?1:-1);} paint(); }); });
    tblEl.querySelectorAll("tr.pe-main").forEach(function(tr){ tr.addEventListener("click",function(){ var idx=tr.getAttribute("data-pe"); var open=false; tblEl.querySelectorAll("tr.pe-ic[data-ic-of='"+idx+"']").forEach(function(x){ var sh=x.style.display==="none"; x.style.display=sh?"":"none"; open=sh; }); var car=tr.querySelector(".pe-caret"); if(car)car.innerHTML=open?"&#9662;":"&#9656;"; }); });
    tblEl.querySelectorAll("td.icnm").forEach(function(td){ td.addEventListener("click",function(e){ e.stopPropagation(); openReport(td.getAttribute("data-icname")); }); });
  }
  paint();
}'''

AUTOSEL_OLD = 'function autoSelectICs(){sA=new Set(ALL_ADVISORS);D.advisors.forEach(function(a){if(calcAttainment(cmAll(a)).avgWeighted==null)sA.delete(a.name);});}'
AUTOSEL_NEW = 'function autoSelectICs(){sA=new Set(ALL_ADVISORS.filter(function(n){return !DEFAULT_OFF.has(n)}));D.advisors.forEach(function(a){if(calcAttainment(cmAll(a)).avgWeighted==null)sA.delete(a.name);});}'


def apply(html):
    applied = []
    # 1. poolTeam/rawFor/dScore/dEmail globals (inserted before renderPE)
    if "function poolTeam(team){" not in html and "function renderPE(rows){" in html:
        html = html.replace("function renderPE(rows){", HELPERS + "function renderPE(rows){", 1)
        applied.append("helpers")
    # 2. autoSelectICs off-list fix
    if AUTOSEL_OLD in html:
        html = html.replace(AUTOSEL_OLD, AUTOSEL_NEW, 1)
        applied.append("autoSelectICs-offlist")
    # 3. replace renderPE with the unified sortable table (if not already applied)
    if "window.__peSortK" not in html and "function renderPE(rows){" in html:
        i = html.find("function renderPE(rows){")
        j = html.find("// ============ SUGGESTED RATING", i)
        if j > 0:
            k = html.rfind("}", i, j)
            if k > i:
                html = html[:i] + RENDERPE + html[k + 1:]
                applied.append("renderPE-sortable-table")
    return html, applied


REQUIRED = {
    "function poolTeam(team){": "pooled roll-up helpers",
    "window.__peSortK": "sortable PE table",
    "class='pe-tbl'": "PE metric columns",
    "!DEFAULT_OFF.has(n)": "autoSelectICs off-list fix",
}


def verify(html):
    return [why for m, why in REQUIRED.items() if m not in html]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    html = path.read_text(encoding="utf-8")
    html, applied = apply(html)
    path.write_text(html, encoding="utf-8")
    missing = verify(html)
    print("advising_pe_patches: applied " + (", ".join(applied) if applied else "nothing (already current)"))
    if missing:
        sys.exit("ERROR: Advising PE customizations missing after patch: " + ", ".join(missing))
    print("verify OK: pooled sortable PE table + off-list fix present")


if __name__ == "__main__":
    main()
