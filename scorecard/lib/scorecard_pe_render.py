#!/usr/bin/env python3
"""Render PE-level scorecard: (A) one expandable table per PE across fiscal quarters,
(B) side-by-side PE-column matrix for THIS quarter only (expandable). Reads scorecard_pe_data.json,
writes _scorecard_pe_combined.html (self-contained fragment) + standalone BenOps_Scorecard_PE_<Mon><Yr>.html."""
import os,json
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,"scorecard_pe_data.json")))
PES=d["pes"]; Q=d["quarters"]; ML=d["ml"]; COV=d["coverage"]; MONTHS=d["months"]
qlabels={"Q3 FY26":"Nov–Jan '26","Q4 FY26":"Feb–Apr '26","Q1 FY27":"May–Jul '26","Q2 FY27":"Aug–Oct '26"}
for q in Q: q["l"]=qlabels.get(q["id"],q["id"])
LASTQ=Q[-1]   # this quarter
mon=MONTHS[-1]; import datetime
MN=datetime.date(int(mon[:4]),int(mon[5:7]),1).strftime("%b%Y")

payload={"PES":PES,"Q":Q,"ML":ML,"LASTQ":LASTQ["id"],"COV":COV}

CSS="""<style>
.pe *{box-sizing:border-box}.pe{font-size:12px}
.pe h2{font-size:14px;font-weight:600;margin:4px 0 2px;color:var(--text-primary)}
.pe h3{font-size:13px;margin:14px 0 5px;font-weight:600;color:var(--text-primary)}
.pe .sub{color:var(--text-muted);font-size:11px;font-weight:400}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 10px}
.bar button{font:inherit;font-size:12px;padding:4px 10px;border:.5px solid var(--border-strong);background:transparent;color:var(--text-primary);border-radius:6px;cursor:pointer}
.bar button.on{background:var(--text-primary);color:var(--bg-primary,#fff)}
.lg{display:flex;gap:10px;font-size:11px;color:var(--text-secondary);margin-left:auto}.lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.team{margin:0 0 16px}.team h4{font-size:12.5px;margin:0 0 4px;font-weight:600;color:var(--text-primary)}.team h4 .t{color:var(--text-muted);font-weight:400;font-size:11px}
.wrap{overflow-x:auto;border:.5px solid var(--border);border-radius:8px}
.pe table{border-collapse:collapse;width:100%}
.pe th,.pe td{padding:4px 6px;text-align:center;border-bottom:.5px solid var(--border);white-space:nowrap}
.pe th{font-weight:500;color:var(--text-secondary);font-size:11px}
.pe td.l,.pe th.l{text-align:left;min-width:220px;padding-left:8px;color:var(--text-primary)}
.pe td.s,.pe th.s{color:var(--text-secondary);font-size:10.5px;min-width:44px}
.pe td.q,.pe th.q{font-weight:500;border-left:1.5px solid var(--border-strong);min-width:62px}
.pe th.q{cursor:pointer;color:var(--text-primary)}
.pe th .qs{display:block;font-size:9.5px;font-weight:400;color:var(--text-muted)}
.pe td.m,.pe th.m{min-width:50px;font-size:11px}
.pe td.pcol,.pe th.pcol{border-left:1.5px solid var(--border-strong);min-width:70px;font-weight:500}
.pe th.pcol .qs{display:block;font-size:9.5px;font-weight:400;color:var(--text-muted)}
.pe td.v{font-family:var(--font-mono)}
.pe tr.sec td{text-align:left;padding:7px 8px 3px;font-size:10.5px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:var(--text-accent);background:var(--surface-1)}
.g{background:var(--bg-success);color:var(--text-success)}.a{background:var(--bg-warning);color:var(--text-warning)}.r{background:var(--bg-danger);color:var(--text-danger)}
.pe tr.d td{font-size:10.5px}.pe tr.d td.l{padding-left:24px;color:var(--text-secondary)}
.pe tr.p{cursor:pointer}.ch{display:inline-block;width:10px;font-size:9px;color:var(--text-accent);transition:transform .12s}.op .ch{transform:rotate(90deg)}
.nt{font-size:10.5px;color:var(--text-muted);line-height:1.5;margin-top:6px}
.pe .na{color:var(--text-faint,#bbb)}
</style>"""

BODY="""
<div class="pe">
<h2>Benefit Services Scorecard — by PE <span class="sub">(leadership layer · Oct 2026)</span></h2>
<div class="nt">PE = your direct leadership layer. <b>Aman Bhatia</b> column = the NP&amp;R leads who report to you for now (Adrienne Reese, Kelly Peacock, Alex Dillon, Brooke Murawski) — ex-Rehana; this is already how OWNER_PEPE is set in-source. Owned-work metrics key off each record's current PEPE. Phone &amp; email are attributed to each IC's <b>current</b> PE via a name/email/agent→PE resolver (coverage: availability <b>__COVA__%</b>, abandon <b>__COVB__%</b>, email <b>__COVE__%</b>; unmapped excluded). Oct '26 is month-to-date — read Sep '26 and the Q2 FY27 QTD column as reliable.</div>

<h3>A · Each PE across fiscal quarters <span class="sub">— click a quarter to expand to months; ▸ rows expand to sub-statuses</span></h3>
<div class="bar"><button id="aQ" class="on">Quarters only</button><button id="aM">Quarters + months</button>
<span class="lg"><span><i style="background:var(--bg-success)"></i>at/above SLO</span><span><i style="background:var(--bg-warning)"></i>near</span><span><i style="background:var(--bg-danger)"></i>below</span></span></div>
<div id="secA"></div>

<h3 style="border-top:.5px solid var(--border);padding-top:12px">B · PEs side by side — this quarter (__LASTQ__ · Aug–Oct '26) <span class="sub">— ▸ rows expand to sub-statuses</span></h3>
<div class="bar"><button id="bExp">Expand all sub-statuses</button><span class="sub">blank cell = metric not owned by that PE</span></div>
<div id="secB"></div>
<div class="nt">Cells are cumulative Q2 FY27 QTD (Σnumerator ÷ Σdenominator, Aug–Oct). RAG by each row's SLO. Net MRR Retention % shown only as a percent. Phone abandon SLO ≤30%.</div>
</div>
"""

SCRIPT="""<script>
const D=__PAYLOAD__;
const PES=D.PES, Q=D.Q, ML=D.ML, LASTQ=D.LASTQ;
function qsum(c,idx){let n=0,dd=0;idx.forEach(i=>{if(c[i]&&c[i][1]){n+=c[i][0];dd+=c[i][1];}});return dd?[n,dd]:null;}
function val(pair,k){if(!pair)return null;const[n,dd]=pair;if(!dd)return null;return (k==='s'||k==='r')?n/dd:100*n/dd;}
function fmt(v,k){if(v==null)return'–';if(k==='p')return Math.round(v);if(k==='p1')return v.toFixed(1);if(k==='r')return v.toFixed(2);if(k==='s')return v.toFixed(2);return Math.round(v);}
function rag(v,r){if(v==null)return'';const g=r.gr!=null?r.gr:r.g;const a=r.am!=null?r.am:(r.d==='hi'?g*0.88:g*1.25);return r.d==='hi'?(v>=g?'g':(v>=a?'a':'r')):(v<=g?'g':(v<=a?'a':'r'));}
function slo(r){return (r.d==='hi'?'≥':'≤')+(r.k[0]==='p'?r.g+'%':r.g);}

/* ---------- Section A: per-PE tables ---------- */
const openA={};Q.forEach(q=>openA[q.id]=false);
function cellsA(c,r){let h='';Q.forEach(q=>{const qp=qsum(c,q.idx),v=val(qp,r.k);h+='<td class="v q '+rag(v,r)+'">'+fmt(v,r.k)+'</td>';if(openA[q.id])q.idx.forEach(i=>{const v2=val(c[i],r.k);h+='<td class="v m '+rag(v2,r)+'">'+fmt(v2,r.k)+'</td>';});});return h;}
function ncolsA(){return 2+Q.reduce((a,q)=>a+1+(openA[q.id]?q.idx.length:0),0);}
function renderA(){let html='',rid=0;
 PES.forEach(pe=>{let h='<div class="team"><h4>'+pe.name+' <span class="t">· '+pe.team+'</span></h4><div class="wrap"><table><thead><tr><th class="l">Metric</th><th class="s">SLO</th>';
  Q.forEach(q=>{h+='<th class="q" data-q="'+q.id+'">'+(openA[q.id]?'▾ ':'▸ ')+q.id+'<span class="qs">'+q.l+'</span></th>';if(openA[q.id])q.idx.forEach(i=>h+='<th class="m">'+ML[i]+'</th>');});
  h+='</tr></thead><tbody>';let sec=null;
  pe.rows.forEach(r=>{if(r.sec!==sec){sec=r.sec;h+='<tr class="sec"><td colspan="'+ncolsA()+'">'+sec+'</td></tr>';}
   const id='A'+(rid++);const det=r.det&&r.det.length;
   h+='<tr'+(det?' class="p" data-d="'+id+'"':'')+'><td class="l">'+(det?'<span class="ch">▶</span> ':'')+r.n+'</td><td class="s">'+slo(r)+'</td>'+cellsA(r.c,r)+'</tr>';
   if(det)r.det.forEach(s=>{h+='<tr class="d" data-p="'+id+'" style="display:none"><td class="l">'+s.n+'</td><td class="s">—</td>'+cellsA(s.c,r)+'</tr>';});});
  html+=h+'</tbody></table></div></div>';});
 const root=document.getElementById('secA');root.innerHTML=html;
 root.querySelectorAll('th.q').forEach(th=>th.onclick=()=>{openA[th.dataset.q]=!openA[th.dataset.q];syncA();renderA();});
 root.querySelectorAll('tr.p').forEach(tr=>tr.onclick=()=>{const rs=root.querySelectorAll('tr[data-p="'+tr.dataset.d+'"]');const s=rs[0].style.display==='none';rs.forEach(x=>x.style.display=s?'table-row':'none');tr.classList.toggle('op',s);});}
function syncA(){document.getElementById('aM').classList.toggle('on',Q.every(q=>openA[q.id]));document.getElementById('aQ').classList.toggle('on',Q.every(q=>!openA[q.id]));}
document.getElementById('aQ').onclick=()=>{Q.forEach(q=>openA[q.id]=false);syncA();renderA();};
document.getElementById('aM').onclick=()=>{Q.forEach(q=>openA[q.id]=true);syncA();renderA();};

/* ---------- Section B: side-by-side (this quarter) ---------- */
const QIDX=Q.find(q=>q.id===LASTQ).idx;
// union of rows across PEs, keep section + per-PE lookup + det
function buildRows(){
 const order=[],seen={};
 PES.forEach(pe=>pe.rows.forEach(r=>{if(!(r.n in seen)){seen[r.n]={n:r.n,sec:r.sec,k:r.k,g:r.g,gr:r.gr,am:r.am,d:r.d,dets:{}};order.push(r.n);}
   const o=seen[r.n];o[pe.name]=r.c;if(r.det&&r.det.length){r.det.forEach(s=>{o.dets[s.n]=o.dets[s.n]||{};o.dets[s.n][pe.name]=s.c;});}}));
 return order.map(n=>seen[n]);
}
const BR=buildRows();let expB=false;
function renderB(){let html='<div class="wrap"><table><thead><tr><th class="l">Metric</th><th class="s">SLO</th>';
 PES.forEach(pe=>html+='<th class="pcol">'+pe.name.split(' ')[0]+'<span class="qs">'+pe.team.replace(' Onboarding','')+'</span></th>');
 html+='</tr></thead><tbody>';let sec=null,rid=0;
 BR.forEach(r=>{if(r.sec!==sec){sec=r.sec;html+='<tr class="sec"><td colspan="'+(2+PES.length)+'">'+sec+'</td></tr>';}
  const detNames=Object.keys(r.dets);const hasdet=detNames.length>0;const id='B'+(rid++);
  html+='<tr'+(hasdet?' class="p" data-d="'+id+'"':'')+'><td class="l">'+(hasdet?'<span class="ch">▶</span> ':'')+r.n+'</td><td class="s">'+slo(r)+'</td>';
  PES.forEach(pe=>{const c=r[pe.name];if(!c){html+='<td class="pcol na">·</td>';return;}const v=val(qsum(c,QIDX),r.k);html+='<td class="v pcol '+rag(v,r)+'">'+fmt(v,r.k)+'</td>';});
  html+='</tr>';
  detNames.forEach(dn=>{html+='<tr class="d" data-p="'+id+'" style="display:'+(expB?'table-row':'none')+'"><td class="l">'+dn+'</td><td class="s">—</td>';
   PES.forEach(pe=>{const c=r.dets[dn][pe.name];if(!c){html+='<td class="pcol na">·</td>';return;}const v=val(qsum(c,QIDX),r.k);html+='<td class="v pcol '+rag(v,r)+'">'+fmt(v,r.k)+'</td>';});html+='</tr>';});
 });
 const root=document.getElementById('secB');root.innerHTML=html+'</tbody></table></div>';
 root.querySelectorAll('tr.p').forEach(tr=>tr.onclick=()=>{const rs=root.querySelectorAll('tr[data-p="'+tr.dataset.d+'"]');const s=rs[0].style.display==='none';rs.forEach(x=>x.style.display=s?'table-row':'none');tr.classList.toggle('op',s);});}
document.getElementById('bExp').onclick=function(){expB=!expB;this.classList.toggle('on',expB);this.textContent=expB?'Collapse sub-statuses':'Expand all sub-statuses';renderB();};
renderA();renderB();
</script>"""

frag=CSS+BODY.replace("__COVA__",str(COV.get("availability"))).replace("__COVB__",str(COV.get("abandon"))).replace("__COVE__",str(COV.get("email"))).replace("__LASTQ__",LASTQ["id"])+SCRIPT.replace("__PAYLOAD__",json.dumps(payload,ensure_ascii=False))
open(os.path.join(HERE,"_scorecard_pe_combined.html"),"w",encoding="utf-8").write(frag)
standalone='<!doctype html><html><head><meta charset="utf-8"><title>BenOps Scorecard — by PE</title><style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;--text-primary:#1a1a1a;--text-secondary:#555;--text-muted:#888;--text-accent:#5b5bd6;--border:#e3e3e0;--border-strong:#c8c8c4;--surface-1:#f6f6f4;--bg-success:#d7f0dd;--text-success:#17663a;--bg-warning:#fcefcf;--text-warning:#8a5a00;--bg-danger:#fbdcdc;--text-danger:#9b1c1c;--bg-primary:#fff;--font-mono:ui-monospace,Menlo,monospace}</style></head><body>'+frag+'</body></html>'
open(os.path.join(HERE,"BenOps_Scorecard_PE_%s.html"%MN),"w",encoding="utf-8").write(standalone)
print("wrote _scorecard_pe_combined.html (%d bytes) and BenOps_Scorecard_PE_%s.html"%(len(frag),MN))
