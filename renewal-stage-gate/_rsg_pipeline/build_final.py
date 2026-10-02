# -*- coding: utf-8 -*-
import json, datetime, os
P    = os.path.dirname(os.path.abspath(__file__))
HTML = P + "/renewal-gate-check-tool.html"
BUN  = P + "/rsg_bundles.json"
COH  = P + "/cohort.json"
OUT  = os.path.dirname(P) + "/renewal-stage-gating-check.html"

orig = open(HTML).read()
style = orig[orig.index("<style>")+7 : orig.index("</style>")]
script = orig[orig.index("<script>")+8 : orig.rindex("</script>")]
script = script.replace('let html = "";', 'if(window.RSG_COMPUTE){return rows;}\n  let html = "";', 1)
for line in ['$("#runBtn").addEventListener("click", run);',
             '$("#opp").addEventListener("keydown", e=>{ if(e.key==="Enter") run(); });',
             'try { const last = localStorage.getItem("gateOpp"); if(last) $("#opp").value = last; } catch(e){}']:
    script = script.replace(line, "")

# --- always show Renewal ID + Hippo link alongside the Opp link in company info ---
anchor = """'<div><div class="k">Opportunity</div><div class="v"><a href="https://gusto.lightning.force.com/'+esc(o.Id)+'" target="_blank" rel="noopener">'+esc(o.Id)+'</a></div></div>'"""
addcells = anchor + """+
    '<div><div class="k">Renewal ID</div><div class="v">'+esc(d.RID||"—")+'</div></div>'+
    '<div><div class="k">Hippo</div><div class="v">'+((o.Account&&o.Account.ZP_Company_ID__c)?('<a href="https://hippo.gusto.com/companies/'+esc(o.Account.ZP_Company_ID__c)+'" target="_blank" rel="noopener">Open in Hippo</a>'):'—')+'</div></div>'"""
assert anchor in script, "meta anchor not found"
script = script.replace(anchor, addcells, 1)

bundles = json.load(open(BUN))

# COHORT comes from cohort.json (written by the SF phase + snow-freshness step),
# so the baked page always reflects the live cohort, not a hardcoded snapshot.
COHORT = json.load(open(COH))
# Canonical Snowflake table→check provenance (display only); load stamp merged in by the snow-freshness step.
SNOW_TABLES = [
    ["EXPIRING_POLICIES / BENEFITS_PLANS / CARRIERS","line, carrier, state, successor","3A,6A,7A,10A"],
    ["QUOTING_PERIODS + quoting config","prior & renewal scheme","3A"],
    ["CARRIER_REGISTRY_* ","allowed calculators & waiting periods","6A,7A"],
    ["UNDERWRITING_RULES_*","min enrolled, in-state, group size","10A"],
    ["SUBSCRIPTIONS / POLICIES","prior-year enrollment","10A"],
    ["COMPANIES","address (flag), work states, headcount","9A,10A"]]
COHORT.setdefault("snow", {})
COHORT["snow"].setdefault("load", "pending")
COHORT["snow"]["tables"] = SNOW_TABLES

LF_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Renewal Stage Gate — Gate 1 (Advising → OA)</title>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>__ORIGSTYLE__</style>
<style>
body{font-family:'Bricolage Grotesque',system-ui,sans-serif;background:#F7F4F2;color:#222525;font-size:13px}
.wrap{display:none}
.sticky-header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid #ececec;padding:13px 28px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.sticky-header h1{font-size:15px;font-weight:800;color:#222525;display:flex;align-items:center;gap:9px;margin:0;border:0}
.sticky-header h1 .dot-logo{width:9px;height:9px;border-radius:50%;background:#088081;box-shadow:0 0 0 3px rgba(8,128,129,.15)}
.sticky-header h1 .tl{color:#088081}
.hdr-right{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.hmeta{font-size:11px;color:#9ca3af}
.verbadge{display:inline-block;vertical-align:middle;margin-left:10px;font:700 9.5px 'JetBrains Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:#088081;background:#eef2ff;border:1px solid #c7d2fe;border-radius:5px;padding:2px 7px;position:relative;top:-2px}
.page{padding:16px 28px 64px;max-width:1120px;margin:0 auto}
.section-lbl{font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin:16px 2px 8px}
/* compact cohort strip */
.cstrip{display:flex;gap:20px;flex-wrap:wrap;align-items:baseline;background:#FFF;border:1px solid #ececec;border-radius:13px;padding:11px 18px}
.cstrip .ci{display:flex;gap:7px;align-items:baseline}
.cstrip .cv{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:16px;line-height:1}
.cstrip .cl{font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.5px}
.cstrip .sep{width:1px;align-self:stretch;background:#eee}
.cstrip .ci.gate .cv{color:#F45D48}
/* slim freshness line + collapsed detail */
.fresh{display:flex;gap:22px;flex-wrap:wrap;font-size:11px;color:#6b7280;margin:9px 2px 2px}
.fresh b{color:#222525;font-weight:700}
.fresh .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle}
details.srcdet{margin:2px 2px 4px}
details.srcdet summary{cursor:pointer;font-size:9.5px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:.6px;padding:3px 0}
details.srcdet[open] summary{color:#088081}
.srcgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:6px}
@media(max-width:820px){.srcgrid{grid-template-columns:1fr}}
.prov{width:100%;border-collapse:collapse;font-size:10px}
.prov caption{text-align:left;font-size:10px;font-weight:700;color:#374151;padding:0 0 4px}
.prov th{font-size:8.5px;font-weight:700;color:#b0b4ba;text-transform:uppercase;letter-spacing:.4px;padding:3px 6px;text-align:left;border-bottom:1px solid #ececec}
.prov td{padding:3px 6px;border-bottom:1px solid #f6f6f6;vertical-align:top;color:#4b5563}
.prov td.mono{font-family:'JetBrains Mono',monospace;color:#088081;white-space:nowrap}
.prov td .chk{display:inline-block;background:#eef1f6;color:#47566b;border-radius:4px;font-size:8.5px;font-weight:700;padding:0 4px;margin:1px}
.searchwrap{background:#FFF;border:1px solid #ececec;border-radius:14px;padding:13px 18px;margin:4px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.searchwrap .sl{font-size:11px;font-weight:700;color:#222525;text-transform:uppercase;letter-spacing:.6px}
#result .card,#result table,#result .review-summary,#result .stat{border-radius:13px!important;border-color:#ececec!important}
#result td.chk{color:#088081}
#result th{background:#fcfcfc;color:#9ca3af}
.pill{border-radius:99px!important}
.pill.PASS{background:rgba(22,128,74,.10);color:#16804a}
.pill.FAIL{background:rgba(199,57,47,.10);color:#c7392f}
.pill.REVIEW{background:#FFF4E0;color:#b8860b}
.pill.MANUAL{background:#eef1f6;color:#47566b}
.pill.NA{background:#eef0f1;color:#8a919b}
.stat.fail .n{color:#c7392f}.stat.pass .n{color:#16804a}.stat.review .n{color:#b8860b}
.controls input{flex:1 1 320px;border-radius:20px;border:1px solid #e5e7eb;font-family:'Bricolage Grotesque',sans-serif}
.controls input:focus{border-color:#088081;box-shadow:0 0 0 3px rgba(8,128,129,.08)}
button.run{background:#088081;border-radius:20px;font-family:'Bricolage Grotesque',sans-serif}
button.run:hover{background:#0a9596}
a{color:#088081}
.status.info{background:rgba(8,128,129,.06);color:#0a6b6c;border-color:rgba(8,128,129,.2)}
</style></head><body>"""

HEADER = """
<div class="sticky-header">
  <h1><span class="dot-logo"></span><span class="tl">Renewal Stage Gate</span>&nbsp;— Gate 1 (Advising → OA)<span class="verbadge">alpha</span></h1>
  <div class="hdr-right"><span class="hmeta" id="genmeta"></span></div>
</div>
<div class="page">
  <div class="cstrip" id="cstrip"></div>
  <div class="fresh" id="fresh"></div>
  <details class="srcdet"><summary>Source fields &amp; tables ▾</summary>
    <div class="srcgrid"><table class="prov" id="sfProv"></table><table class="prov" id="snProv"></table></div>
  </details>
  <div class="section-lbl">Run a gate check</div>
  <div class="searchwrap"><span class="sl">Opp lookup</span>
    <div class="controls" style="flex:1;display:flex;gap:10px">
      <input id="opp" type="text" placeholder="e.g. Aflow  ·  Philip Ngai  ·  Squared  ·  207780" />
      <button id="runBtn" class="run">Run gate check</button>
    </div>
  </div>
  <div id="status" class="status"></div>
  <div id="result"></div>
  <div class="foot" style="color:#9aa1ab;font-size:11px;margin-top:16px">Gate 1 applies at <strong>ER Confirm</strong>. Verdicts are the original deterministic checks over embedded, nightly-refreshed data — no live connectors. 2A notes and 9A address are reduced to derived status.</div>
</div>"""

CTRL = """
<script>
const RSG = __BUNDLES__;
const RSG_SCHEME = RSG.scheme;
const COHORT = __COHORT__;
(function(){
  window.RSG_COMPUTE=false; var B=RSG.bundles;
  document.getElementById('genmeta').textContent='Data as of '+COHORT.generated;
  var byS={}; COHORT.stages.forEach(function(s){byS[s[0]]=s[1];});
  function ci(v,l,cls){return '<div class="ci '+(cls||'')+'"><span class="cv">'+v+'</span><span class="cl">'+l+'</span></div>';}
  document.getElementById('cstrip').innerHTML=
    ci(COHORT.total.toLocaleString(),'in-scope')+'<span class="sep"></span>'+
    ci((byS['ER Confirm']||0).toLocaleString(),'ER Confirm','gate')+
    ci((byS['Engaged']||0).toLocaleString(),'Engaged')+
    ci((byS['Recommendation Sent']||0).toLocaleString(),'Rec Sent')+
    ci((byS['Alternatives Requested']||0).toLocaleString(),'Alt Req')+'<span class="sep"></span>'+
    ci(Math.round(100*COHORT.novdec/COHORT.total)+'%','renew Nov–Dec');
  document.getElementById('fresh').innerHTML=
    '<span><span class="dot" style="background:#00A1E0"></span>Salesforce — <b>current to '+COHORT.sf.asof+'</b></span>'+
    '<span><span class="dot" style="background:#29B5E8"></span>Snowflake — <b>nightly load '+COHORT.snow.load+'</b></span>';
  prov('sfProv','Salesforce (pulled at bake)',['Object','Updated','Fields','Chk'],COHORT.sf.objects);
  prov('snProv','Snowflake (Hawaiian Ice)',['Table(s)','Fields','Chk'],COHORT.snow.tables);
  function prov(id,cap,head,rows){
    var h='<caption>'+cap+'</caption><tr>'+head.map(function(x){return '<th>'+x+'</th>';}).join('')+'</tr>';
    h+=rows.map(function(r){var chk=r[r.length-1].split(/,\\s*/).map(function(c){return '<span class="chk">'+c+'</span>';}).join('');
      var mid=r.slice(0,r.length-1).map(function(c,i){return '<td'+(i===1&&r.length===4?' class="mono"':'')+'>'+esc(c)+'</td>';}).join('');
      return '<tr>'+mid+'<td>'+chk+'</td></tr>';}).join('');
    document.getElementById(id).innerHTML=h;
  }
  function prep(e){ if(!e.d.schemeSheet) e.d.schemeSheet=parseSchemeSheet(RSG_SCHEME); return e; }
  function resolve(raw){ raw=(raw||'').trim(); if(!raw) return null; var ids=Object.keys(B);
    for(var i=0;i<ids.length;i++){ var e=B[ids[i]], s=(e.o.Source_ID__c||'');
      if(ids[i]===raw||s===raw) return ids[i];
      if(/^\\d+$/.test(raw)&&s.endsWith('renewal-'+raw)) return ids[i];
      if((e.o.Account.Name||'').toLowerCase().indexOf(raw.toLowerCase())>=0) return ids[i]; }
    return null; }
  window.run=function(){ var oid=resolve(document.getElementById('opp').value);
    if(!oid){ setStatus('No opp in this baked sample matched \\u2014 try Aflow, Philip Ngai, Squared, or 207780.','err'); return; }
    var e=prep(B[oid]); window.RSG_COMPUTE=false; setStatus(''); render(e.o,e.d);
    try{ document.getElementById('result').scrollIntoView({behavior:'smooth',block:'start'}); }catch(x){} };
  document.getElementById('runBtn').addEventListener('click',window.run);
  document.getElementById('opp').addEventListener('keydown',function(ev){ if(ev.key==='Enter') window.run(); });
})();
</script>"""

page = (LF_HEAD.replace("__ORIGSTYLE__", style) + HEADER
        + "\n<script>" + script + "</script>\n"
        + CTRL.replace("__BUNDLES__", json.dumps(bundles, separators=(",",":")))
              .replace("__COHORT__", json.dumps(COHORT, separators=(",",":")))
        + "\n</body></html>")
open(OUT,"w").write(page)
print("WROTE", OUT, len(page), "bytes")
