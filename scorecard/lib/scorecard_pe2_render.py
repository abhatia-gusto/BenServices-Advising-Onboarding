#!/usr/bin/env python3
"""Render team-lead-level PE scorecard, grouped by leader.
(A) per-PE tables across fiscal quarters, grouped under each leader; (B) per-leader side-by-side
PE-column matrix for THIS quarter only, expandable. Reads scorecard_pe2_data.json.
Writes _scorecard_pe2_combined.html + standalone BenOps_Scorecard_PEbyLead_<Mon><Yr>.html."""
import os,json,datetime
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,"scorecard_pe2_data.json")))
Q=d["quarters"]; ML=d["ml"]; COV=d["coverage"]; MONTHS=d["months"]; LEAD=d["leaders"]
qlabels={"Q3 FY26":"Nov–Jan '26","Q4 FY26":"Feb–Apr '26","Q1 FY27":"May–Jul '26","Q2 FY27":"Aug–Oct '26"}
for q in Q: q["l"]=qlabels.get(q["id"],q["id"])
LASTQ=Q[-1]["id"]
MN=datetime.date(int(MONTHS[-1][:4]),int(MONTHS[-1][5:7]),1).strftime("%b%Y")
payload={"LEAD":LEAD,"Q":Q,"ML":ML,"LASTQ":LASTQ}

CSS="""<style>
.pe *{box-sizing:border-box}.pe{font-size:12px}
.pe h2{font-size:14px;font-weight:600;margin:4px 0 2px;color:var(--text-primary)}
.pe h3{font-size:13px;margin:14px 0 6px;font-weight:600;color:var(--text-primary)}
.pe .sub{color:var(--text-muted);font-size:11px;font-weight:400}
.grp{margin:10px 0 4px;padding:4px 8px;background:var(--surface-2,var(--surface-1));border-radius:6px;font-size:12px;font-weight:600;color:var(--text-primary)}
.grp .r{color:var(--text-muted);font-weight:400;font-size:11px}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 10px}
.bar button{font:inherit;font-size:12px;padding:4px 10px;border:.5px solid var(--border-strong);background:transparent;color:var(--text-primary);border-radius:6px;cursor:pointer}
.bar button.on{background:var(--text-primary);color:var(--bg-primary,#fff)}
.lg{display:flex;gap:10px;font-size:11px;color:var(--text-secondary);margin-left:auto}.lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.team{margin:0 0 12px}.team h4{font-size:12px;margin:0 0 4px;font-weight:600;color:var(--text-primary)}
.wrap{overflow-x:auto;border:.5px solid var(--border);border-radius:8px}
.pe table{border-collapse:collapse;width:100%}
.pe th,.pe td{padding:4px 6px;text-align:center;border-bottom:.5px solid var(--border);white-space:nowrap}
.pe th{font-weight:500;color:var(--text-secondary);font-size:11px}
.pe td.l,.pe th.l{text-align:left;min-width:210px;padding-left:8px;color:var(--text-primary)}
.pe td.s,.pe th.s{color:var(--text-secondary);font-size:10.5px;min-width:42px}
.pe td.q,.pe th.q{font-weight:500;border-left:1.5px solid var(--border-strong);min-width:60px}
.pe th.q{cursor:pointer;color:var(--text-primary)}
.pe th .qs{display:block;font-size:9.5px;font-weight:400;color:var(--text-muted)}
.pe td.m,.pe th.m{min-width:48px;font-size:11px}
.pe td.pcol,.pe th.pcol{border-left:1.5px solid var(--border-strong);min-width:66px;font-weight:500}
.pe td.agg,.pe th.agg{border-left:2.5px solid var(--text-primary,#333);font-weight:700}
.pe th.pcol .qs{display:block;font-size:9.5px;font-weight:400;color:var(--text-muted)}
.pe td.v{font-family:var(--font-mono)}
.pe tr.sec td{text-align:left;padding:6px 8px 3px;font-size:10px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:var(--text-accent);background:var(--surface-1)}
.g{background:var(--bg-success);color:var(--text-success)}.a{background:var(--bg-warning);color:var(--text-warning)}.r2{background:var(--bg-danger);color:var(--text-danger)}
.pe tr.d td{font-size:10.5px}.pe tr.d td.l{padding-left:24px;color:var(--text-secondary)}
.pe tr.p{cursor:pointer}.ch{display:inline-block;width:10px;font-size:9px;color:var(--text-accent);transition:transform .12s}.op .ch{transform:rotate(90deg)}
.nt{font-size:10.5px;color:var(--text-muted);line-height:1.5;margin-top:6px}
.pe .na{color:var(--text-faint,#bbb)}
</style>"""

BODY="""
<div class="pe">
<h2>Benefit Services Scorecard — by PE (team lead) <span class="sub">· Oct 2026</span></h2>
<div class="nt"><b>PE = the IC's direct manager (team lead).</b> PEs are grouped under their leader (your directs): Micah, Lynne, Lee Ann, Martin — and <b>Aman</b> directly for the ex-Rehana NP&amp;R leads (Kelly, Adrienne, Alex, Brooke). Grouping is each record's current OWNER_PEPE in-source. Phone &amp; email are attributed to each IC's <b>current</b> PE (team lead) via a name/email/agent→PE resolver (coverage: availability <b>__COVA__%</b>, abandon <b>__COVB__%</b>, email <b>__COVE__%</b>; unmapped excluded). All data points reconcile: Σ PEs = leader = team = the Benefit Services scorecard (max diff 0.1pp, from the small unmapped phone/email share). Oct '26 is month-to-date — read Sep '26 and the Q2 FY27 QTD column.</div>

<h3>A · Each PE across fiscal quarters, grouped by leader <span class="sub">— click a quarter to expand to months; ▸ rows expand to sub-statuses</span></h3>
<div class="bar"><button id="aQ" class="on">Quarters only</button><button id="aM">Quarters + months</button>
<span class="lg"><span><i style="background:var(--bg-success)"></i>at/above SLO</span><span><i style="background:var(--bg-warning)"></i>near</span><span><i style="background:var(--bg-danger)"></i>below</span></span></div>
<div id="secA"></div>

<h3 style="border-top:.5px solid var(--border);padding-top:12px">B · PEs side by side within each leader — this quarter (__LASTQ__ · Aug–Oct '26) <span class="sub">— ▸ rows expand to sub-statuses</span></h3>
<div class="bar"><button id="bExp">Expand all sub-statuses</button></div>
<div id="secB"></div>
<div class="nt">Cells are cumulative Q2 FY27 QTD (Σnumerator ÷ Σdenominator, Aug–Oct). RAG by each row's SLO. Phone abandon SLO ≤30%. Net MRR Retention shown as % only.</div>
</div>
"""

SCRIPT="""<script>
const D=__PAYLOAD__;const LEAD=D.LEAD,Q=D.Q,ML=D.ML,LASTQ=D.LASTQ;
function qsum(c,idx){let n=0,dd=0;idx.forEach(i=>{if(c[i]&&c[i][1]){n+=c[i][0];dd+=c[i][1];}});return dd?[n,dd]:null;}
function val(p,k){if(!p)return null;const[n,dd]=p;if(!dd)return null;return (k==='s'||k==='r')?n/dd:100*n/dd;}
function fmt(v,k){if(v==null)return'–';if(k==='p')return Math.round(v);if(k==='p1')return v.toFixed(1);if(k==='r')return v.toFixed(2);if(k==='s')return v.toFixed(2);return Math.round(v);}
function rag(v,r){if(v==null)return'';const g=r.gr!=null?r.gr:r.g;const a=r.am!=null?r.am:(r.d==='hi'?g*0.88:g*1.25);const c=r.d==='hi'?(v>=g?'g':(v>=a?'a':'r2')):(v<=g?'g':(v<=a?'a':'r2'));return c;}
function slo(r){return (r.d==='hi'?'≥':'≤')+(r.k[0]==='p'?r.g+'%':r.g);}

/* Section A */
const openA={};Q.forEach(q=>openA[q.id]=false);
function cellsA(c,r){let h='';Q.forEach(q=>{const v=val(qsum(c,q.idx),r.k);h+='<td class="v q '+rag(v,r)+'">'+fmt(v,r.k)+'</td>';if(openA[q.id])q.idx.forEach(i=>{const v2=val(c[i],r.k);h+='<td class="v m '+rag(v2,r)+'">'+fmt(v2,r.k)+'</td>';});});return h;}
function ncolsA(){return 2+Q.reduce((a,q)=>a+1+(openA[q.id]?q.idx.length:0),0);}
function renderA(){let html='',rid=0;
 LEAD.forEach(L=>{html+='<div class="grp">'+L.name+' <span class="r">· '+(L.direct?'reports to Aman directly':'reports to Aman')+' · '+L.pes.length+' PEs</span></div>';
  L.pes.forEach(pe=>{let h='<div class="team"><h4>'+pe.name+'</h4><div class="wrap"><table><thead><tr><th class="l">Metric</th><th class="s">SLO</th>';
   Q.forEach(q=>{h+='<th class="q" data-q="'+q.id+'">'+(openA[q.id]?'▾ ':'▸ ')+q.id+'<span class="qs">'+q.l+'</span></th>';if(openA[q.id])q.idx.forEach(i=>h+='<th class="m">'+ML[i]+'</th>');});
   h+='</tr></thead><tbody>';let sec=null;
   pe.rows.forEach(r=>{if(r.sec!==sec){sec=r.sec;h+='<tr class="sec"><td colspan="'+ncolsA()+'">'+sec+'</td></tr>';}
    const id='A'+(rid++);const det=r.det&&r.det.length;
    h+='<tr'+(det?' class="p" data-d="'+id+'"':'')+'><td class="l">'+(det?'<span class="ch">▶</span> ':'')+r.n+'</td><td class="s">'+slo(r)+'</td>'+cellsA(r.c,r)+'</tr>';
    if(det)r.det.forEach(s=>{h+='<tr class="d" data-p="'+id+'" style="display:none"><td class="l">'+s.n+'</td><td class="s">—</td>'+cellsA(s.c,r)+'</tr>';});});
   html+=h+'</tbody></table></div></div>';});});
 const root=document.getElementById('secA');root.innerHTML=html;
 root.querySelectorAll('th.q').forEach(th=>th.onclick=()=>{openA[th.dataset.q]=!openA[th.dataset.q];syncA();renderA();});
 root.querySelectorAll('tr.p').forEach(tr=>tr.onclick=()=>{const rs=root.querySelectorAll('tr[data-p="'+tr.dataset.d+'"]');const s=rs[0].style.display==='none';rs.forEach(x=>x.style.display=s?'table-row':'none');tr.classList.toggle('op',s);});}
function syncA(){document.getElementById('aM').classList.toggle('on',Q.every(q=>openA[q.id]));document.getElementById('aQ').classList.toggle('on',Q.every(q=>!openA[q.id]));}
document.getElementById('aQ').onclick=()=>{Q.forEach(q=>openA[q.id]=false);syncA();renderA();};
document.getElementById('aM').onclick=()=>{Q.forEach(q=>openA[q.id]=true);syncA();renderA();};

/* Section B — per leader, PE columns, this quarter */
const QIDX=Q.find(q=>q.id===LASTQ).idx;let expB=false;
function leaderRows(L){const order=[],seen={};
 L.pes.forEach(pe=>pe.rows.forEach(r=>{if(!(r.n in seen)){seen[r.n]={n:r.n,sec:r.sec,k:r.k,g:r.g,gr:r.gr,am:r.am,d:r.d,dets:{},cols:{}};order.push(r.n);}
  const o=seen[r.n];o.cols[pe.name]=r.c;if(r.det)r.det.forEach(s=>{o.dets[s.n]=o.dets[s.n]||{};o.dets[s.n][pe.name]=s.c;});}));
 return order.map(n=>seen[n]);}
function aggCols(m,k){let n=0,dd=0;for(const nm in m){const c=m[nm];if(!c)continue;QIDX.forEach(i=>{if(c[i]&&c[i][1]){n+=c[i][0];dd+=c[i][1];}});}if(!dd)return null;return (k==='s'||k==='r')?n/dd:100*n/dd;}
function renderB(){let html='',gid=0;
 LEAD.forEach(L=>{html+='<div class="grp">'+L.name+' <span class="r">· '+(L.direct?'reports to Aman directly':'reports to Aman')+'</span></div>';
  const BR=leaderRows(L);html+='<div class="wrap"><table><thead><tr><th class="l">Metric</th><th class="s">SLO</th>';
  L.pes.forEach(pe=>html+='<th class="pcol">'+pe.name+'</th>');html+='<th class="pcol agg">\u03a3 '+L.name.split(' ')[0]+'</th>';html+='</tr></thead><tbody>';let sec=null;
  BR.forEach(r=>{if(r.sec!==sec){sec=r.sec;html+='<tr class="sec"><td colspan="'+(3+L.pes.length)+'">'+sec+'</td></tr>';}
   const dn=Object.keys(r.dets);const hd=dn.length>0;const id='B'+(gid++);
   html+='<tr'+(hd?' class="p" data-d="'+id+'"':'')+'><td class="l">'+(hd?'<span class="ch">▶</span> ':'')+r.n+'</td><td class="s">'+slo(r)+'</td>';
   L.pes.forEach(pe=>{const c=r.cols[pe.name];const v=c?val(qsum(c,QIDX),r.k):null;html+='<td class="v pcol '+rag(v,r)+'">'+(c?fmt(v,r.k):'·')+'</td>';});
   {const av=aggCols(r.cols,r.k);html+='<td class="v pcol agg '+rag(av,r)+'">'+fmt(av,r.k)+'</td>';}
   html+='</tr>';
   dn.forEach(s=>{html+='<tr class="d" data-p="'+id+'" style="display:'+(expB?'table-row':'none')+'"><td class="l">'+s+'</td><td class="s">—</td>';
    L.pes.forEach(pe=>{const c=r.dets[s][pe.name];const v=c?val(qsum(c,QIDX),r.k):null;html+='<td class="v pcol '+rag(v,r)+'">'+(c?fmt(v,r.k):'·')+'</td>';});{const av=aggCols(r.dets[s],r.k);html+='<td class="v pcol agg '+rag(av,r)+'">'+fmt(av,r.k)+'</td>';}html+='</tr>';});});
  html+='</tbody></table></div>';});
 const root=document.getElementById('secB');root.innerHTML=html;
 root.querySelectorAll('tr.p').forEach(tr=>tr.onclick=()=>{const rs=root.querySelectorAll('tr[data-p="'+tr.dataset.d+'"]');const s=rs[0].style.display==='none';rs.forEach(x=>x.style.display=s?'table-row':'none');tr.classList.toggle('op',s);});}
document.getElementById('bExp').onclick=function(){expB=!expB;this.classList.toggle('on',expB);this.textContent=expB?'Collapse sub-statuses':'Expand all sub-statuses';renderB();};
renderA();renderB();
</script>"""

frag=CSS+BODY.replace("__COVA__",str(COV.get("availability"))).replace("__COVB__",str(COV.get("abandon"))).replace("__COVE__",str(COV.get("email"))).replace("__LASTQ__",LASTQ)+SCRIPT.replace("__PAYLOAD__",json.dumps(payload,ensure_ascii=False))
open(os.path.join(HERE,"_scorecard_pe2_combined.html"),"w",encoding="utf-8").write(frag)
standalone='<!doctype html><html><head><meta charset="utf-8"><title>BenOps Scorecard — by PE (team lead)</title><style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1250px;margin:24px auto;padding:0 16px;--text-primary:#1a1a1a;--text-secondary:#555;--text-muted:#888;--text-accent:#5b5bd6;--border:#e3e3e0;--border-strong:#c8c8c4;--surface-1:#f6f6f4;--surface-2:#eeeeec;--bg-success:#d7f0dd;--text-success:#17663a;--bg-warning:#fcefcf;--text-warning:#8a5a00;--bg-danger:#fbdcdc;--text-danger:#9b1c1c;--bg-primary:#fff;--font-mono:ui-monospace,Menlo,monospace}</style></head><body>'+frag+'</body></html>'
open(os.path.join(HERE,"BenOps_Scorecard_PEbyLead_%s.html"%MN),"w",encoding="utf-8").write(standalone)
print("wrote _scorecard_pe2_combined.html (%d bytes) and BenOps_Scorecard_PEbyLead_%s.html"%(len(frag),MN))
