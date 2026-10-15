import json
import html as _html
from gen8_head import CSS
DATA_JSON=json.dumps(json.load(open('oa_data.json')),separators=(',',':'))

# ── Data Resources tab: advising-style SQL segment catalog (source-of-truth queries) ──
def _read_sql(fn):
    try:
        return open(fn,encoding='utf-8').read().strip()
    except Exception as e:
        return '-- (could not read '+fn+': '+str(e)+')'

_SS='https://share-some-html.staging.zp-int.com/'
_HUB_URL=_SS+'advising-onboarding-dashboards'
# Mirrors the Advising & Onboarding dashboard hub — links verified against that page.
_HUB=[
 ('SLA',[('Benefit Order SLA',_SS+'bo-sla-dashboard'),
         ('Advising SLA',_SS+'advising-sla-dashboard'),
         ('Broker Onboarding SLA',_SS+'broker-onboarding-sla-dashboard'),
         ('Ticket SLA by Flow',_SS+'ticket-sla-by-flow'),
         ('Email SLA',_SS+'benefit-services-email-sla'),
         ('Phone Dashboard',_SS+'advising-onboarding-phone')]),
 ('Performance',[('Advising Performance',_SS+'advising-performance-dashboard'),
         ('New Plan &amp; Renewal Performance',_SS+'npr-onboarding-performance'),
         ('Broker Onboarding Performance',_SS+'broker-onboarding-performance'),
         ('Advising Net MRR',_SS+'advising-mrr-dashboard'),
         ('Level Funded',_SS+'benefit-services-level-funded-conversion'),
         ('Key NPR Operating Metrics',_SS+'key-npr-operating-metrics-cohort')]),
 ('Quality',[('Level AI QA','https://redash.zp-int.com/queries/156897'),
             ('AB Maestro Dashboard','https://redash.zp-int.com/dashboards/6643-ab-maestro-dashboard')]),
 ('Customer Experience',[('BenOps CSAT + In-App',_SS+'benefit-services-csat-dashboard')]),
]

# (category, [ (seg_id, name, main_table, joins, grain, powers, params, sql_file) ])
_SEGMENTS=[
 ('SLA Delivery',[
   ('bo_grain','Benefit Order SLA &mdash; OA Held / Cancel / Ticket-rate denom','BI_REPORTING.BENEFIT_ORDERS',
    'BENEFIT_ORDER_STATUS_CHANGE_HISTORY &middot; GUSTO_EMPLOYEES &middot; SFDC_USERS_GUSTO_EMPLOYEES_VIEW','one row per benefit order',
    'BO Status (OA Held) &middot; New Plan Cancel &middot; Ticket Rate','2026-01-01 &rarr; CURRENT_DATE()','q_bo_v2.sql'),
   ('ticket_sla','Ticket SLA','bi.sfdc_tickets',
    'bi_reporting.benefit_orders &middot; bi.gusto_employees &middot; sfdc_users_gusto_employees_view','one row per OA-attributed ticket',
    'Ticket SLA','2026-01-01 &rarr; CURRENT_DATE()','q_ticketsla_v4.sql'),
   ('availability','Phone Availability','bi.wfm_agent_activity_log_details',
    'bi.people_analytics_workday_time_tracking &middot; bi.gusto_employees','team &times; IC &times; month',
    'Phone Availability','2026-01-01 &rarr; CURRENT_DATE()','q_avail.sql'),
   ('abandon','Abandon &mdash; team (queue level)','BI.PHONE_QUEUE_METRICS',
    '&mdash;','queue &times; month','Abandon (mod.) &mdash; team roll-up','2026-01-01 &rarr; CURRENT_DATE()','q_abandon.sql'),
   ('abandon_ic','Abandon &mdash; per IC','bi.phone_user_metrics &middot; bi.phone_calls',
    'bi.gusto_employees','IC &times; month','Abandon (mod.) &mdash; per-IC','2026-01-01 &rarr; CURRENT_DATE()','q_abandon_ic.sql')]),
 ('Quality',[
   ('level_ai_qa','Level AI QA','bi.fct_level_ai_conversation_asr_log',
    'bi.cases &middot; bi.gusto_employees','one row per QA&rsquo;d conversation (pooled qa_score / max_qa_score)',
    'Level AI QA','2026-01-01 &rarr; CURRENT_DATE()','q_qa.sql')]),
 ('Diagnostics (VoC &middot; Email &middot; Maestro)',[
   ('csat','CSAT','BI_REPORTING.CES_CSAT_DATA',
    'BENEFIT_ORDERS &middot; GUSTO_EMPLOYEES &middot; SFDC_USERS_GUSTO_EMPLOYEES_VIEW','one row per CSAT survey',
    'CSAT (diagnostic)','2026-01-01 &rarr; CURRENT_DATE()','q_csat_rows.sql'),
   ('email_sla','Email SLA (4hr HOOP)','bi.benefit_order_touchpoints',
    'bi.benefit_orders &middot; bi.cases &middot; bi.sfdc_opportunity_history &middot; bi.gusto_employees','one row per inbound email touchpoint',
    'Email SLA (diagnostic)','2026-01-01 &rarr; CURRENT_DATE()','q_email_ic.sql'),
   ('maestro','Maestro Adherence','BI_REPORTING.BENEFIT_ORDERS',
    'BENEFIT_ORDER_STATUS_CHANGE_HISTORY &middot; GUSTO_EMPLOYEES','one row per eligible benefit order',
    'Maestro Adherence (diagnostic)','2026-01-01 &rarr; CURRENT_DATE()','q_maestro_ic.sql')]),
 ('Roster',[
   ('roster','Roster &amp; PE map','BI.GUSTO_EMPLOYEES (current_flag=TRUE)',
    'self-join on PE_SFDC_EE_ID &rarr; current PE name','one row per active IC (NPR + OA)',
    'Grouping &middot; PE','current snapshot (no date window)','q_roster.sql')]),
]

def _build_res_html():
    p=['<div class="card drx"><h2>Data Resources</h2>'
       '<p class="sub" style="font-size:12px;color:var(--gt);line-height:1.55;max-width:820px;margin-bottom:6px">'
       'Everything behind this dashboard in one place &mdash; the source-dashboard hub, plus the exact query behind each metric. '
       'Copy &amp; run in Redash, the Snowflake MCP, or Claude. Params are inclusive date windows; runs on GUSTIE_ADHOC_WH, America/Denver.</p>']
    hub='<div class="dr-hub"><div class="dr-ey">Source dashboards</div>'\
        '<h3>Benefit Services &mdash; Advising &amp; Onboarding dashboard hub</h3>'\
        '<div class="dr-url">'+_HUB_URL+'</div>'\
        '<a class="dr-btn" href="'+_HUB_URL+'" target="_blank" rel="noopener">Open the dashboard hub &rarr;</a>'\
        '<div class="dr-grid">'
    for col,links in _HUB:
        hub+='<div class="dr-col"><h4>'+col+'</h4>'+''.join('<a href="'+u+'" target="_blank" rel="noopener">'+n+'</a>' for n,u in links)+'</div>'
    hub+='</div></div>'
    p.append(hub)
    for cat,segs in _SEGMENTS:
        p.append('<div class="dr-cat">'+cat+'</div>')
        for sid,name,main,joins,grain,powers,params,fn in segs:
            sql=_html.escape(_read_sql(fn))
            op=''
            p.append('<div class="dr-card'+op+'" data-seg="'+sid+'">'
                     '<div class="dr-h"><div class="dr-name">'+name+'</div><span class="dr-car">&#9654;</span></div>'
                     '<div class="dr-b"><dl class="dr-dl">'
                     '<dt>Main table</dt><dd><code>'+main+'</code></dd>'
                     '<dt>Joins</dt><dd><code>'+joins+'</code></dd>'
                     '<dt>Grain</dt><dd>'+grain+'</dd>'
                     '<dt>Powers</dt><dd>'+powers+'</dd>'
                     '<dt>Params</dt><dd><code>'+params+'</code></dd></dl>'
                     '<div class="dr-note">Canonical pipeline query <code>'+fn+'</code> &mdash; run verbatim; change only the date window.</div>'
                     '<div class="dr-codewrap"><button class="dr-copy" type="button">Copy</button><pre class="dr-pre">'+sql+'</pre></div>'
                     '</div></div>')
    p.append('</div>')
    return ''.join(p)

RES_HTML=_build_res_html()

DR_CSS=(
 '#tab-resources .drx{max-width:1000px}'
 '#tab-resources .dr-hub{background:linear-gradient(180deg,#ffffff,#f6fbf7);border:1px solid var(--ln,#e6ded2);'
 'border-left:5px solid var(--teal,#2f7d4f);border-radius:12px;padding:18px 20px;margin:6px 0}'
 '#tab-resources .dr-ey{font-size:11.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--teal,#1f5c39)}'
 '#tab-resources .dr-hub h3{margin:4px 0 2px;font-size:18px;color:var(--dk,#1f2a24)}'
 '#tab-resources .dr-url{font-size:13px;color:var(--teal,#2f7d4f);word-break:break-all;margin-top:2px}'
 '#tab-resources .dr-btn{display:inline-block;margin-top:10px;background:var(--teal,#2f7d4f);color:#fff;text-decoration:none;font-weight:700;font-size:13px;padding:9px 16px;border-radius:8px}'
 '#tab-resources .dr-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:16px 0 2px}'
 '#tab-resources .dr-col h4{font-size:11.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--teal,#1f5c39);'
 'margin:0 0 6px;border-bottom:2px solid var(--ln,#e6ded2);padding-bottom:4px}'
 '#tab-resources .dr-col a{display:block;font-size:12.5px;color:var(--dk,#1f2a24);text-decoration:none;padding:3px 0}'
 '#tab-resources .dr-col a:hover{text-decoration:underline}'
 '#tab-resources .dr-note{color:#6b7a72;font-size:12px;margin:2px 0 10px}'
 '#tab-resources .dr-cat{font-size:13px;font-weight:800;color:var(--teal,#1f5c39);letter-spacing:.09em;text-transform:uppercase;'
 'margin:22px 0 6px;padding-bottom:6px;border-bottom:2px solid var(--ln,#e6ded2)}'
 '#tab-resources .dr-card{background:#fff;border:1px solid var(--ln,#e6ded2);border-left:4px solid var(--teal,#2f7d4f);'
 'border-radius:10px;margin:9px 0;overflow:hidden}'
 '#tab-resources .dr-h{display:flex;align-items:center;gap:12px;padding:12px 15px;cursor:pointer;user-select:none}'
 '#tab-resources .dr-h:hover{background:#fbfdfb}'
 '#tab-resources .dr-name{font-weight:700;font-size:14.5px;color:var(--dk,#1f2a24)}'
 '#tab-resources .dr-car{margin-left:auto;transition:transform .15s;color:#6b7a72;font-size:12px}'
 '#tab-resources .dr-card.open .dr-car{transform:rotate(90deg)}'
 '#tab-resources .dr-b{display:none;border-top:1px solid var(--ln,#e6ded2);padding:6px 15px 15px}'
 '#tab-resources .dr-card.open .dr-b{display:block}'
 '#tab-resources .dr-dl{display:grid;grid-template-columns:120px 1fr;gap:4px 14px;margin:11px 2px 12px;font-size:13px}'
 '#tab-resources .dr-dl dt{color:#6b7a72;font-weight:600}'
 '#tab-resources .dr-dl dd{margin:0;color:var(--dk,#1f2a24)}'
 '#tab-resources .dr-dl code{background:#eef3ee;padding:1px 6px;border-radius:4px;font-size:11.5px}'
 '#tab-resources .dr-codewrap{position:relative}'
 '#tab-resources .dr-copy{position:absolute;top:8px;right:8px;background:var(--teal,#2f7d4f);color:#fff;border:0;border-radius:6px;'
 'padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}'
 '#tab-resources pre.dr-pre{margin:0;background:#0f1c17;color:#e8f0ea;border-radius:8px;padding:14px 16px;overflow:auto;'
 'font-size:12px;line-height:1.5;max-height:360px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}'
)
CSS=CSS.replace('</style>', DR_CSS+'</style>')

JS=r'''
var DATA=__DATA__;
var ML=(function(){var N=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];var o={};(DATA.months||[]).forEach(function(m){o[m]=N[+m.split('-')[1]-1];});return o;})();
var AREAS=[{k:'sla',l:'SLA Delivery',c:'#088081',metrics:['phone_avail','abandon','ticket_sla','oa_held']},
 {k:'qual',l:'Quality',c:'#7a5ea8',metrics:['qa','ticket_rate']},
 {k:'cancel',l:'Cancel',c:'#c96a1e',metrics:['np_cancel']}];
var ORDER=AREAS.reduce(function(a,x){return a.concat(x.metrics)},[]);
var AREAOF={};AREAS.forEach(function(a){a.metrics.forEach(function(k){AREAOF[k]=a})});
var FIRSTOF={};AREAS.forEach(function(a){FIRSTOF[a.metrics[0]]=1});
var LASTOF={};AREAS.forEach(function(a){LASTOF[a.metrics[a.metrics.length-1]]=a.k});
var WREL={phone_avail:1,abandon:1,ticket_sla:1,oa_held:1,qa:1,ticket_rate:1,np_cancel:1};
function areaWsum(ar){return ar.metrics.reduce(function(s,k){return s+WREL[k]},0);}
var NCOLS=3+ORDER.length+AREAS.length+3+2+4;
var QPR_PASS=83.3;
var MLABEL={},DM={};DATA.metrics.forEach(function(m){DM[m.key]=m;MLABEL[m.key]={l:m.label,short:m.short,d:(m.dir==='lower'?'lte':'gte'),g:m.goal,fp:m.floor_pct,fmt:m.fmt}});
function defS(){var o={metrics:{}};ORDER.forEach(function(k){if(k==='ticket_rate'){var dm=DM.ticket_rate;o.metrics[k]={gnp:dm.goal,grn:dm.goal_rn,fnp:dm.floor,frn:dm.floor_rn};}else{var m=MLABEL[k];o.metrics[k]={g:m.g,f:m.d==='lte'?+(m.g/(m.fp/100)).toFixed(0):+(m.g*m.fp/100).toFixed(0)};}});return o;}
var S=defS();
// Shared metric definition table — single source for modal methodology + Calc tab (prevents drift).
var MDEF={phone_avail:'Of eligible days in the period, the percent at 80–105% availability (minimum 2 hours logged).',abandon:'Of inbound calls in the period, the percent abandoned, excluding remove-from-queue.',ticket_sla:'Of Ful→OA tickets closed in the period, the percent closed within 5 days. Closed = ticket has a close date (any status).',oa_held:'Of benefit orders closed in the period (fulfilled or cancelled), the percent that met every OA-held stage entered, at 1 day or less each. Orders that never entered an OA stage are excluded.',qa:'Average QA score across Level AI conversations evaluated in the period.',ticket_rate:'OA tickets per benefit order fulfilled in the period, scored separately for New Plan and Renewal+Change, then blended by volume.',np_cancel:'Of New-Plan orders closed in the period, the percent that cancelled.'};
function dirArrow(k){return k==='phone_avail'?'↔':((MLABEL[k]&&MLABEL[k].d==='lte')?'↓':'↑');}
var ORIGINAL_TITLE=document.title;
var ratingFilter=null;
var state={tab:'performance',months:DATA.months.slice(),pe:[],adv:[],q:'',sort:'weighted',dir:-1,collapsed:{sla:true,qual:true,cancel:true,diag:true},peOpen:{}};
var $=function(id){return document.getElementById(id)};
function selMonths(){if(state.months.length===1&&state.months[0]==='~')return [];return state.months.length?state.months:DATA.months;}

var DIAG=[{k:'csat',l:'CSAT'},{k:'email_sla',l:'Email SLA'},{k:'maestro',l:'Maestro Adherence'}];
function escHtml(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function diagVal(a,k){var ms=selMonths();
 if(k==='csat'){var s=0,n=0;ms.forEach(function(m){s+=a.months[m].cs_s||0;n+=a.months[m].cs_n||0});return {v:(n>=1?s/n:null),n:n};}
 if(k==='maestro'){var mn=0,md=0;ms.forEach(function(m){mn+=a.months[m].ma_n||0;md+=a.months[m].ma_d||0});return {v:(md>=1?100*mn/md:null),n:md};}
 var mt=0,d=0;ms.forEach(function(m){mt+=a.months[m].em_n||0;d+=a.months[m].em_d||0});return {v:(d>=1?100*mt/d:null),n:d};}
function diagBand(k,v){if(v==null)return 'var(--gt)';if(k==='csat')return v>=4.5?'var(--gn)':v>=3.9?'#d9a441':v>=3.0?'var(--amber)':'var(--rd)';if(k==='maestro')return v>=90?'var(--gn)':v>=80?'var(--teal)':v>=70?'var(--amber)':'var(--rd)';return v>=80?'var(--gn)':v>=60?'var(--teal)':v>=40?'var(--amber)':'var(--rd)';}
function diagFmt(k,v){return v==null?'—':(k==='csat'?v.toFixed(2):v.toFixed(1)+'%');}
function teamDiag(t,k){var s=0,n=0,mt=0,d=0,mn=0,md=0;t.forEach(function(r){selMonths().forEach(function(m){if(k==='csat'){s+=r.a.months[m].cs_s||0;n+=r.a.months[m].cs_n||0;}else if(k==='maestro'){mn+=r.a.months[m].ma_n||0;md+=r.a.months[m].ma_d||0;}else{mt+=r.a.months[m].em_n||0;d+=r.a.months[m].em_d||0;}})});return k==='csat'?(n>=1?s/n:null):(k==='maestro'?(md>=1?100*mn/md:null):(d>=1?100*mt/d:null));}
function repDiag(r){var cs=diagVal(r.a,'csat'),em=diagVal(r.a,'email_sla'),ma=diagVal(r.a,'maestro');
 var cards='<div class="diag-cards"><div class="diag-card"><div class="diag-lbl">CSAT (1–5)</div><div class="diag-val" style="color:'+diagBand('csat',cs.v)+'">'+(cs.v==null?'—':cs.v.toFixed(2))+'</div>'+(cs.v==null?'<div class="diag-sub">no surveys</div>':'<div class="diag-sub">'+cs.n+' responses</div>')+'</div><div class="diag-card"><div class="diag-lbl">Email SLA (4h)</div><div class="diag-val" style="color:'+diagBand('email_sla',em.v)+'">'+(em.v==null?'—':em.v.toFixed(1)+'%')+'</div>'+(em.v==null?'<div class="diag-sub">no emails</div>':'<div class="diag-sub">'+Math.round(em.v/100*em.n)+' / '+em.n+' within SLA</div>')+'</div><div class="diag-card"><div class="diag-lbl">Maestro Adherence</div><div class="diag-val" style="color:'+diagBand('maestro',ma.v)+'">'+(ma.v==null?'—':ma.v.toFixed(1)+'%')+'</div>'+(ma.v==null?'<div class="diag-sub">no RFSP-eligible orders</div>':'<div class="diag-sub">'+Math.round(ma.v/100*ma.n)+' / '+ma.n+' orders all tasks done</div>')+'</div></div>';
 var sm=selMonths();var cm=(r.a.comments||[]).filter(function(x){return sm.indexOf((x.d||'').slice(0,7))>=0;});var ch='';
 if(cm.length){function li(x){return '<li><span class="diag-comment-score s-'+x.s+'">'+x.s+'</span><span class="diag-comment-text">'+escHtml(x.c)+'</span><span class="diag-comment-date">'+x.d+'</span></li>';}
   ch='<div class="diag-comments-h">CSAT comments <span class="diag-n">('+cm.length+' total)</span></div><ul class="diag-comments">'+cm.map(li).join('')+'</ul>';}
 return '<div class="rep-section diag-section"><h3>Diagnostic Measures <span class="rep-pill">not scored</span></h3><div style="font-size:12px;color:var(--dk);margin-bottom:10px">These measures provide additional context beyond the scored metrics. They\'re not part of Avg Weighted or QPR but inform the broader performance picture and feed into the formal rating review.<br><b>CSAT</b> — customer satisfaction score (1–5) after case resolution. Attributed to the benefit-order owner (New Plan + Renewal).<br><b>Email SLA</b> — % of inbound emails responded to within 4 business hours (HOOP). Attributed to the BO owner at time of touchpoint.<br><b>Maestro Adherence</b> — of Maestro-eligible benefit orders that entered RFSP in the month, the % with all Maestro tasks complete. Attributed to the BO owner; bucketed by RFSP-entry month.</div>'+cards+ch+'</div>';}
function rawVal(a,k){
 var ms=selMonths();
 if(k==='phone_avail'){var s=0,n=0;ms.forEach(function(m){s+=a.months[m].av_s;n+=a.months[m].av_d});return n?100*s/n:null;}
 if(k==='abandon'){var n=0,dd=0;ms.forEach(function(m){n+=a.months[m].ab_n;dd+=a.months[m].ab_d});if(dd<1)return null;return 100*n/dd;}
 if(k==='qa'){var s=0,n=0;ms.forEach(function(m){s+=a.months[m].qa_s;n+=a.months[m].qa_n});return n?s/n:null;}
 var mp={ticket_sla:['ts_n','ts_d'],oa_held:['oa_n','oa_d'],ticket_np:['tnp_n','tnp_d'],ticket_rn:['trn_n','trn_d'],np_cancel:['nc_n','nc_d']}[k];
 var N=0,D=0;ms.forEach(function(m){N+=a.months[m][mp[0]];D+=a.months[m][mp[1]]});
 if(k==='ticket_sla'&&D<5)return null;
 if((k==='ticket_np'||k==='ticket_rn')&&D<5)return null;
 if(k==='np_cancel'&&D<10)return null;
 return D?100*N/D:null;
}
function denomOf(a,k){var ms=selMonths();var mp={ticket_sla:['ts_n','ts_d'],oa_held:['oa_n','oa_d'],ticket_np:['tnp_n','tnp_d'],ticket_rn:['trn_n','trn_d'],np_cancel:['nc_n','nc_d']}[k];if(!mp)return null;var D=0;ms.forEach(function(m){D+=a.months[m][mp[1]]});return D;}
function poolRatio(a,n,dn){var N=0,D=0;selMonths().forEach(function(m){N+=a.months[m][n];D+=a.months[m][dn]});return D?N/D:null;}
function attain(k,v){if(v==null)return null;var g=+S.metrics[k].g;if(!g)return null;var m=MLABEL[k];return m.d==='lte'?Math.min(v===0?125:g/v*100,125):Math.min(v/g*100,125);}
function statOf(k,v){if(v==null)return null;var g=+S.metrics[k].g,f=+S.metrics[k].f,m=MLABEL[k];return m.d==='lte'?(v<=g?'goal':v<=f?'floor':'miss'):(v>=g?'goal':v>=f?'floor':'miss');}
function poolRate(a,n,dn){var N=0,D=0;selMonths().forEach(function(m){N+=a.months[m][n];D+=a.months[m][dn]});return D?100*N/D:null;}
function poolN(a,f){var s=0;selMonths().forEach(function(m){s+=a.months[m][f]});return s;}
// Ticket Rate: one metric, scored per order type (NP vs Renewal+Change) against different targets, volume-weighted.
// Returns per-type status + attainment so the cell + modal can color each independently.
function tkScore(t){var c=S.metrics.ticket_rate;
 function one(rate,den,g,f){if(rate==null||den<5)return null;var att=Math.min(rate===0?125:g/rate*100,125);var st=rate<=g?'goal':rate<=f?'floor':'miss';return{att:att,den:den,st:st};}
 var np=one(t.np,t.npd,+c.gnp,+c.fnp),rn=one(t.rn,t.rnd,+c.grn,+c.frn);var av=[np,rn].filter(Boolean);
 var base={val:null,att:null,status:null,np:t.np,rn:t.rn,npd:t.npd,rnd:t.rnd,npSt:np?np.st:null,rnSt:rn?rn.st:null,npAtt:np?np.att:null,rnAtt:rn?rn.att:null};
 if(!av.length)return base;
 var den=av.reduce(function(s,x){return s+x.den},0);
 var att=av.reduce(function(s,x){return s+x.att*x.den},0)/den;
 var status=av.some(function(x){return x.st==='miss'})?'miss':(av.every(function(x){return x.st==='goal'})?'goal':'floor');
 base.att=Math.round(att*10)/10;base.status=status;return base;}
function scoreVals(getVal,getTicket){var m={};ORDER.forEach(function(k){if(k==='ticket_rate'){m[k]=tkScore(getTicket());}else{var v=getVal(k);m[k]={val:v,att:attain(k,v),status:statOf(k,v)};}});
 var area={},areaG={},wW=0,wQ=0,sW=0;
 AREAS.forEach(function(ar){var av=ar.metrics.filter(function(k){return m[k].att!=null});
   if(!av.length){area[ar.k]=null;return;}
   var ws=av.reduce(function(s,k){return s+WREL[k]},0);
   var sc=av.reduce(function(s,k){return s+WREL[k]*Math.min(m[k].att,125)},0)/ws;
   var miss=ar.metrics.some(function(k){return m[k].status==='miss'});
   area[ar.k]=Math.round(sc*10)/10;areaG[ar.k]=miss?0:area[ar.k];
   var w=100/AREAS.length;wW+=area[ar.k]*w;wQ+=areaG[ar.k]*w;sW+=w;});
 return{m:m,area:area,areaG:areaG,weighted:sW?wW/sW:null,qpr:sW?wQ/sW:null};}
function computeRow(a){var s=scoreVals(function(k){return rawVal(a,k)},function(){return{np:poolRatio(a,'tnp_s','tnp_d'),rn:poolRatio(a,'trn_s','trn_d'),npd:poolN(a,'tnp_d'),rnd:poolN(a,'trn_d')};});return{a:a,name:a.name,pe:a.manager,team:a.team,nOrders:poolN(a,'ord'),m:s.m,area:s.area,areaG:s.areaG,weighted:s.weighted,qpr:s.qpr};}
function areaMiss(r,ar){return ar.metrics.some(function(k){return r.m[k].status==='miss'})}
function filteredAdvisors(){return DATA.ics.filter(function(a){
   if(state.pe.length&&state.pe.indexOf(a.manager)<0)return false;
   if(state.adv.length&&state.adv.indexOf(a.name)<0)return false;
   if(state.q){var q=state.q.toLowerCase();if(a.name.toLowerCase().indexOf(q)<0&&(a.manager||'').toLowerCase().indexOf(q)<0)return false;}
   return true;});}
function rowsComputed(){var rs=filteredAdvisors().map(computeRow).filter(function(r){return r.weighted!=null});assignRatings(rs);return rs;}
// cohort for the modal percentile gauge: Months + PE filters only — NOT the IC pick or table search,
// so opening one IC's report still shows the full peer distribution.
function cohortRows(){return DATA.ics.map(computeRow).filter(function(r){return r.weighted!=null});}  /* full roster, month-aware; PE/IC filters ignored for the percentile pool */
function bandColor(v){return v==null?'var(--gt)':v>=100?'var(--gn)':v>=80?'var(--amber)':'var(--rd)';}
function goalTxt(k){if(k==='ticket_rate'){var c=S.metrics.ticket_rate;return '≤'+(+c.gnp).toFixed(2)+' NP · ≤'+(+c.grn).toFixed(2)+' Rnl/Chg';}var m=MLABEL[k];return (m.d==='gte'?'≥':'≤')+S.metrics[k].g+(m.fmt==='%'?'%':'');}
function floorTxt(k){if(k==='ticket_rate'){var c=S.metrics.ticket_rate;return '≤'+(+c.fnp).toFixed(2)+' NP · ≤'+(+c.frn).toFixed(2)+' Rnl/Chg';}var m=MLABEL[k];return (m.d==='gte'?'≥':'≤')+S.metrics[k].f+(m.fmt==='%'?'%':'');}
function fmtV(k,v){if(v==null)return'—';return v.toFixed(1)+(MLABEL[k].fmt==='%'?'%':'');}
function tkClass(st){return st==='goal'?'tk-g':st==='floor'?'tk-y':st==='miss'?'tk-r':'tk-dot';}
function valText(k,c){
 if(k==='ticket_rate'){if(c.att==null)return '<span class="muted">—</span>';
   var np=c.np==null?'<span class="tk-dot">NP —</span>':'<span class="tk-seg '+tkClass(c.npSt)+'">NP '+c.np.toFixed(2)+'</span>';
   var rn=c.rn==null?'<span class="tk-dot">R+C —</span>':'<span class="tk-seg '+tkClass(c.rnSt)+'">R+C '+c.rn.toFixed(2)+'</span>';
   return np+'<span class="tk-dot"> · </span>'+rn;}
 return fmtV(k,c.val);}

function kpiScore(l,v,sub,cls){return '<div class="kpi accent"><div class="lbl">'+l+'</div><div class="val" style="color:'+(cls||'var(--dk)')+'">'+(v==null?'—':v.toFixed(1)+'%')+'</div><div class="sub">'+sub+'</div></div>';}
function renderKPIs(rows){var sw=rows.filter(function(r){return r.weighted!=null});
 var aw=sw.length?sw.reduce(function(s,r){return s+r.weighted},0)/sw.length:null;
 var aq=sw.length?sw.reduce(function(s,r){return s+r.qpr},0)/sw.length:null;
 var h=kpiScore('Avg Weighted Attainment',aw,'across '+sw.length+' ICs','var(--teal)')+kpiScore('QPR Attainment',aq,'across '+sw.length+' ICs',aq!=null&&aq<80?'var(--rd)':'var(--dk)');
 var bfN=rows.filter(function(r){return ORDER.some(function(k){return r.m[k].status==='miss'})}).length;
 var btN=rows.filter(function(r){return ORDER.some(function(k){return r.m[k].status==='miss'||r.m[k].status==='floor'})}).length;
 h+='<div class="kpi"><div class="lbl">ICs below floor</div><div class="val" style="color:'+(bfN===0?'var(--gt)':'var(--rd)')+'">'+bfN+'</div><div class="sub">of '+rows.length+' · ≥1 metric below floor</div></div>';
 h+='<div class="kpi"><div class="lbl">ICs below target</div><div class="val" style="color:'+(btN===0?'var(--gt)':'var(--amber)')+'">'+btN+'</div><div class="sub">of '+rows.length+' · ≥1 metric below goal</div></div>';
 ORDER.forEach(function(k){var wd=rows.filter(function(r){return r.m[k].att!=null});
   if(!wd.length){h+='<div class="kpi"><div class="lbl">'+MLABEL[k].l+'</div><div class="val muted">—</div><div class="sub">no data</div></div>';return;}
   var met=wd.filter(function(r){return r.m[k].status==='goal'}).length;var bf=wd.filter(function(r){return r.m[k].status==='miss'}).length;
   var pm=Math.round(100*met/wd.length);var good=pm>=70;var col=good?'var(--gn)':pm>=40?'var(--amber)':'var(--rd)';
   h+='<div class="kpi '+(good?'gn':'rd')+'"><div class="lbl">'+MLABEL[k].l+'</div><div class="val" style="color:'+col+'">'+met+'/'+wd.length+'</div><div class="sub">Goal '+goalTxt(k)+' · '+pm+'% met</div>'+'<div class="sub" style="font-weight:700;color:'+(bf>0?'var(--rd)':'var(--gn)')+'">'+bf+' below floor</div>'+'<div class="kbar"><div class="kbar-f" style="width:'+pm+'%;background:'+col+'"></div></div></div>';});
 $('kpis').innerHTML=h;}

function renderHist(rows){var vals=rows.map(function(r){return state.hist==='weighted'?r.weighted:r.qpr}).filter(function(x){return x!=null});
 var bins=[[0,70],[70,80],[80,90],[90,100],[100,110],[110,999]];var cts=bins.map(function(){return 0});
 vals.forEach(function(v){for(var i=0;i<bins.length;i++){if(v>=bins[i][0]&&v<bins[i][1]){cts[i]++;break}}});
 var mx=Math.max.apply(null,cts.concat([1]));
 $('hist').innerHTML=bins.map(function(b,i){var lab=b[1]>900?b[0]+'+':b[0]+'–'+b[1];var col=b[0]<70?'var(--rd)':b[0]<90?'var(--amber)':b[0]<100?'#d9a441':b[0]<110?'var(--teal)':'var(--gn)';
   return '<div class="hbar-wrap"><div class="hct">'+cts[i]+'</div><div class="hbar" style="height:'+(cts[i]/mx*100)+'%;background:'+col+'"></div><div class="hlb">'+lab+'</div></div>';}).join('');
 $('histTitle').textContent='Attainment distribution: '+(state.hist==='weighted'?'Avg Weighted Attainment':'QPR Attainment');
 var avg=vals.length?(vals.reduce(function(s,x){return s+x},0)/vals.length).toFixed(1):'—';
 $('histLegend').innerHTML=vals.length+' ICs · mean '+(state.hist==='weighted'?'Weighted':'QPR')+' <b>'+avg+'%</b> · 100 = meets goal';}

function cell(k,c){var ck=AREAOF[k].k;var cls=(FIRSTOF[k]?'asep ':'')+'col-'+ck+(LASTOF[k]?' aedge-'+ck:'');
 if(!c||c.att==null)return '<td class="'+cls+'"><span class="muted">—</span></td>';
 if(k==='ticket_rate')return '<td class="'+cls+'">'+valText(k,c)+'<span class="attsub">'+c.att.toFixed(1)+'% att</span></td>';
 var ic=c.status==='goal'?'ico-g':c.status==='floor'?'ico-y':'ico-r';
 return '<td class="'+cls+'"><span class="ico '+ic+'">'+valText(k,c)+'</span><span class="attsub">'+c.att.toFixed(1)+'% att</span></td>';}
function scoreCell(v,extra){return '<td class="'+(extra||'')+'"><span class="ascore" style="color:'+bandColor(v)+'">'+(v==null?'—':v.toFixed(1)+'%')+'</span></td>';}
function bfCount(r){return ORDER.filter(function(k){return r.m[k].status==='miss'}).length;}
function btCount(r){return ORDER.filter(function(k){return r.m[k].status==='miss'||r.m[k].status==='floor'}).length;}
function assignRatings(rows){var clean=rows.filter(function(r){return bfCount(r)===0&&r.qpr!=null}).slice().sort(function(a,b){return b.qpr-a.qpr});
 var topN=Math.min(Math.ceil(rows.length*0.15),clean.length);var top3={};clean.slice(0,topN).forEach(function(r){top3[r.name]=1});
 rows.forEach(function(r){if(r.qpr==null&&r.weighted==null)r.rating=null;else if(bfCount(r)>0)r.rating=1;else if(top3[r.name])r.rating=3;else r.rating=2;});}
function ratingChip(r){if(r.rating==null)return '<td class="r div-r" style="text-align:center;color:var(--gt)">—</td>';
 var tip='Suggested Rating '+r.rating+(r.rating===1?' — ≥1 metric below floor':r.rating===3?' — top 15% by QPR (no floor miss)':' — no floor miss, not top 15%')+'. Suggestion only; final rating reflects additional factors.';
 return '<td class="r div-r" style="text-align:center"><span class="rate-chip r'+r.rating+'" title="'+tip+'">'+r.rating+'</span></td>';}
function barCell(v,kind,gated){if(v==null)return '<td style="color:var(--gt)">—</td>';var bw=Math.min(v/125*100,100);var col=(kind==='qpr')?((gated||v<=62.5)?'var(--rd)':v>=100?'var(--gn)':v>=85?'var(--teal)':'var(--amber)'):(v>=100?'var(--gn)':v>=85?'var(--teal)':v>=62.5?'var(--amber)':'var(--rd)');return '<td><div class="att-bar"><div class="att-track"><div class="att-fill" style="width:'+bw+'%;background:'+col+'"></div></div><span class="att-lbl" style="color:'+col+'">'+v.toFixed(1)+'%</span></div></td>';}
function arr(k){return state.sort===k?(state.dir<0?' ↓':' ↑'):' ⇅';}
function renderTbl(rows){
 var th='<tr><th class="fz fz1" data-k="name">IC'+arr('name')+'</th><th class="fz fz2" data-k="pe">PE'+arr('pe')+'</th><th class="fz fz3 r" data-k="nOrders">Orders'+arr('nOrders')+'<span class="colsub">closed</span></th>';
 AREAS.forEach(function(a){var cl=state.collapsed[a.k];var nM=a.metrics.length;
   th+='<th class="area-toggle atgl-'+a.k+(cl?' aedge-'+a.k:'')+'" data-k="area:'+a.k+'" style="color:'+a.c+'">'+a.l.split(' ')[0]+' attn'+arr('area:'+a.k)+'<span class="area-subcta" data-cl="'+a.k+'">'+(cl?'▸ show '+nM+' metric'+(nM>1?'s':''):'▾ hide metrics')+'</span></th>';
   if(!cl)a.metrics.forEach(function(k){var m=MLABEL[k];var gf='Goal '+goalTxt(k)+' · Floor '+floorTxt(k);
     th+='<th data-k="'+k+'" class="col-'+a.k+(FIRSTOF[k]?' asep':'')+(LASTOF[k]?' aedge-'+a.k:'')+'">'+m.short+arr(k)+'<span class="colsub">'+gf+'</span></th>';});});
 th+='<th data-k="belowFloor" class="div-r"># Below Floor'+arr('belowFloor')+'<span class="colsub">metrics below floor</span></th><th data-k="belowTarget" class="div-r"># Below Target'+arr('belowTarget')+'<span class="colsub">metrics below goal</span></th><th data-k="weighted">Avg Weighted Attainment'+arr('weighted')+'<span class="colsub">simple weighted average</span></th><th data-k="qpr" class="div-r">QPR Attainment'+arr('qpr')+'<span class="colsub">area resets to 0% if metric below floor</span></th><th class="r div-r" data-k="rating">Suggested Rating'+arr('rating')+'<span class="colsub">recomputed vs visible set</span></th><th class="diag-toggle diagcol div-l-thick" data-k="" style="color:#534AB7">Diagnostic Measures<span class="area-subcta" data-cl="diag">'+(state.collapsed.diag?'▸ show '+DIAG.length+' measures':'▾ hide')+'</span></th>'+(state.collapsed.diag?'':DIAG.map(function(dm){return '<th class="diagcol" data-k="diag:'+dm.k+'" style="color:#534AB7;cursor:pointer">'+dm.l+arr('diag:'+dm.k)+'<span class="diag-sub">'+(dm.k==='csat'?'avg 1–5':dm.k==='maestro'?'% eligible orders w/ all tasks completed':'% met ≤4hr SLA')+'</span></th>';}).join(''))+'</tr>';
 var tbl=$('icTbl');
 tbl.className='';
 tbl.querySelector('thead').innerHTML=th;
 function v(r){var k=state.sort;if(k==='name')return r.name;if(k==='pe')return r.pe||'';if(k==='weighted')return r.weighted;if(k==='qpr')return r.qpr;if(k==='nOrders')return r.nOrders;if(k==='rating')return r.rating;if(k==='belowFloor')return ORDER.filter(function(x){return r.m[x].status==='miss'}).length;if(k==='belowTarget')return ORDER.filter(function(x){return r.m[x].status==='miss'||r.m[x].status==='floor'}).length;if(k.indexOf('area:')===0)return r.area[k.slice(5)];if(k.indexOf('diag:')===0){var dv=diagVal(r.a,k.slice(5));return dv&&dv.v!=null?dv.v:null;}return r.m[k]?r.m[k].att:null;}
 rows.sort(function(x,y){var a=v(x),b=v(y);if(typeof a==='string')return state.dir*a.localeCompare(b);a=a==null?-1:a;b=b==null?-1:b;return state.dir*(a-b);});
 var tb='';rows.forEach(function(r){
   var row='<tr class="dat" data-ic="'+r.name+'"><td class="fz fz1 nm icnm">'+r.name+'</td><td class="fz fz2"><span class="muted">'+(r.pe||'—')+'</span></td><td class="fz fz3 r muted">'+r.nOrders+'</td>';
   AREAS.forEach(function(a){row+=scoreCell(r.area[a.k],'area-toggle atgl-'+a.k+(state.collapsed[a.k]?' aedge-'+a.k:''));if(!state.collapsed[a.k])a.metrics.forEach(function(k){row+=cell(k,r.m[k])});});
   var bf=ORDER.filter(function(x){return r.m[x].status==='miss'}).length;var bt=ORDER.filter(function(x){return r.m[x].status==='miss'||r.m[x].status==='floor'}).length;
   row+='<td class="cnt div-r" style="color:'+(bf===0?'var(--gt)':'var(--rd)')+'">'+bf+'</td><td class="cnt div-r" style="color:'+(bt===0?'var(--gt)':'var(--amber)')+'">'+bt+'</td>'+barCell(r.weighted,'avg')+barCell(r.qpr,'qpr',ORDER.some(function(k){return r.m[k].status==='miss'}))+ratingChip(r)+'<td class="diagcol div-l-thick"></td>'+(state.collapsed.diag?'':DIAG.map(function(dm){var dv=diagVal(r.a,dm.k);var sub=dv.v==null?'':(dm.k==='csat'?'n='+dv.n:Math.round(dv.v/100*dv.n)+' / '+dv.n);return '<td class="diagcol" style="text-align:center"><span style="font-family:var(--mn);font-weight:700;color:'+diagBand(dm.k,dv.v)+'">'+diagFmt(dm.k,dv.v)+'</span>'+(sub?'<span class="attsub">'+sub+'</span>':'')+'</td>';}).join(''))+'</tr>';tb+=row;});
 $('icTbl').querySelector('tbody').innerHTML=tb||'<tr><td colspan="'+NCOLS+'" class="muted" style="padding:20px;text-align:center">No ICs match.</td></tr>';}

// ===== report modal (Advising-v11 parity) =====
function gaugeInner(gv,pool){
 if(gv==null||pool.length<2)return '<div class="rep-gauge-empty">Distribution unavailable — not enough ICs with data.</div>';
 var srt=pool.slice().sort(function(a,b){return a-b}),N=srt.length;
 function pval(P){var idx=P/100*(N-1),lo=Math.floor(idx),hi=Math.ceil(idx);return lo===hi?srt[lo]:srt[lo]+(srt[hi]-srt[lo])*(idx-lo);}
 var below=0,eq=0;for(var i=0;i<N;i++){if(srt[i]<gv)below++;else if(srt[i]===gv)eq++;}
 var pctl=Math.max(0,Math.min(100,Math.round((below+0.5*eq)/N*100)));
 var h='<div class="rep-gauge-bar">';
 [25,50,75,90].forEach(function(g){h+='<div style="position:absolute;top:-3px;bottom:-3px;left:'+g+'%;width:1px;background:var(--gt);opacity:.5"></div>';});
 h+='<div class="rep-gauge-star" style="left:'+pctl+'%">&#9733;</div></div>';
 h+='<div style="position:relative;height:32px;margin-top:7px">';[25,50,75,90].forEach(function(P){h+='<div style="position:absolute;left:'+P+'%;transform:translateX(-50%);text-align:center"><span style="display:block;font-size:9px;font-weight:700;letter-spacing:.4px;color:var(--gt)">P'+P+'</span><span style="display:block;font-family:var(--mn);font-size:13px;font-weight:800;color:var(--dk);margin-top:1px">'+Math.round(pval(P))+'%</span></div>';});h+='</div>';
 h+='<div style="margin-top:4px;font-size:11px;color:var(--gt);line-height:1.4;text-align:center">&#9733; = you &middot; bars mark the team’s 25th / 50th / 75th / 90th percentile attainment for the selected period</div>';
 return h;}
function gaugeBlock(title,val,pool){return '<div class="rep-gauge"><div class="rep-summary-lbl">'+title+'</div>'+gaugeInner(val,pool)+'<div class="rep-gauge-cap"><span style="color:'+bandColor(val)+'">'+(val==null?'—':val.toFixed(1)+'%')+'</span> <span class="muted">attainment</span></div></div>';}
function repSummaryRow(label,val,note,pool){var col=(val==null)?'var(--gt)':(val>=100?'var(--gn)':val>=85?'var(--teal)':val>=70?'var(--amber)':'var(--rd)');return '<div class="rep-summary"><div class="rep-summary-card"><div class="rep-summary-lbl">'+label+'</div><div class="rep-summary-val" style="color:'+col+'">'+(val==null?'—':val.toFixed(1)+'%')+'</div><div class="rep-summary-note">'+note+'</div></div><div class="rep-gauge">'+gaugeInner(val,pool)+'</div></div>';}
function repChip(st){if(st==null)return '<span class="rep-status-chip na">no data</span>';if(st==='goal')return '<span class="rep-status-chip goal">✓ at or above goal</span>';if(st==='floor')return '<span class="rep-status-chip floor">⚠ between floor and goal</span>';return '<span class="rep-status-chip miss">✗ below floor</span>';}
function repMetricRows(r){function mrow(k){var c=r.m[k];
  var valc;
  if(k==='ticket_rate'){valc=(c.att==null?'—':'NP '+(c.np==null?'—':c.np.toFixed(2))+' · R+C '+(c.rn==null?'—':c.rn.toFixed(2)));}
  else{valc=fmtV(k,c.val);}
  return '<tr><td class="nm">'+dirArrow(k)+' '+MLABEL[k].l+'</td><td class="mono">'+valc+'</td><td>'+goalTxt(k)+'</td><td>'+floorTxt(k)+'</td><td class="r mono">'+(c.att==null?'—':c.att.toFixed(1)+'%')+'</td><td>'+repChip(c.status)+'</td></tr>';}
 return AREAS.map(function(a){return '<tr class="rep-area-row"><td colspan="6" style="color:'+a.c+'">'+a.l+'</td></tr>'+a.metrics.map(mrow).join('');}).join('');}
function repTicketBreak(r){var c=r.m.ticket_rate,S2=S.metrics.ticket_rate;
 var npBO=Math.round(poolN(r.a,'tnp_d')),rnBO=Math.round(poolN(r.a,'trn_d'));
 function row(lbl,rate,bo,att,st,g,f){return '<tr><td class="nm">'+lbl+'</td><td class="mono">'+(rate==null?'—':rate.toFixed(2))+'</td><td class="mono">'+bo+'</td><td>≤'+(+g).toFixed(2)+'</td><td>≤'+(+f).toFixed(2)+'</td><td class="r mono">'+(att==null?'—':att.toFixed(1)+'%')+'</td><td>'+repChip(st)+'</td></tr>';}
 return '<table class="rep-table"><thead><tr><th>Order type</th><th>Tickets / BO</th><th>Fulfilled BOs</th><th>Goal</th><th>Floor</th><th class="r">Attainment</th><th>Status</th></tr></thead><tbody>'+
   row('New Plan',c.np,npBO,c.npAtt,c.npSt,S2.gnp,S2.fnp)+row('Renewal + Change',c.rn,rnBO,c.rnAtt,c.rnSt,S2.grn,S2.frn)+
   '</tbody></table><div class="rep-area-note">Blended attainment '+(c.att==null?'—':c.att.toFixed(1)+'%')+' — volume-weighted by fulfilled BOs. Cell status = worst order type, so a strong renewal rate won\'t mask a New-Plan floor miss.</div>';}
function repAreaSection(r,a){var aa=r.area[a.k];var miss=areaMiss(r,a);
 var head='<h3 style="color:'+a.c+'">'+a.l+'<span class="rep-pill">'+(aa==null?'—':aa.toFixed(1)+'% area')+'</span></h3>'+(miss?'<div class="rep-area-note"><span class="gated">A metric is below floor — this area counts as 0% in QPR.</span></div>':'');
 if(a.k==='qual'){
   var rowsH=a.metrics.map(function(k){var c=r.m[k];var vv=(k==='ticket_rate')?(c.att==null?'—':'blended '+c.att.toFixed(1)+'% att'):fmtV(k,c.val);
     return '<tr><td class="nm">'+MLABEL[k].l+'</td><td class="mono">'+vv+'</td><td>'+goalTxt(k)+'</td><td>'+floorTxt(k)+'</td><td>'+repChip(c.status)+'</td></tr>';}).join('');
   return '<div class="rep-section">'+head+'<table class="rep-table"><thead><tr><th>Metric</th><th>Value</th><th>Goal</th><th>Floor</th><th>Status</th></tr></thead><tbody>'+rowsH+'</tbody></table><div class="rep-area-note" style="margin-top:12px;font-weight:700;color:var(--dk)">Ticket Rate breakdown by order type</div>'+repTicketBreak(r)+'</div>';}
 var rh=a.metrics.map(function(k){var c=r.m[k];return '<tr><td class="nm">'+MLABEL[k].l+'</td><td class="mono">'+fmtV(k,c.val)+'</td><td>'+goalTxt(k)+'</td><td>'+floorTxt(k)+'</td><td class="r mono">'+(c.att==null?'—':c.att.toFixed(1)+'%')+'</td><td>'+repChip(c.status)+'</td></tr>';}).join('');
 return '<div class="rep-section">'+head+'<table class="rep-table"><thead><tr><th>Metric</th><th>Value</th><th>Goal</th><th>Floor</th><th class="r">Attainment</th><th>Status</th></tr></thead><tbody>'+rh+'</tbody></table></div>';}
function repEvidence(r){
 function n(f){return Math.round(poolN(r.a,f));}
 var ord=n('ord'),npd=n('tnp_d'),rnd=n('trn_d'),ncn=n('nc_n'),ncd=n('nc_d'),oan=n('oa_n'),oad=n('oa_d');
 var trNp=poolRatio(r.a,'tnp_s','tnp_d'),trRn=poolRatio(r.a,'trn_s','trn_d');
 var tsd=n('ts_d'),tsn=n('ts_n'),avd=n('av_d'),avs=n('av_s'),abn=n('ab_n'),abd=n('ab_d');
 function row(l,v){return '<div class="rep-ev-row"><span class="rep-ev-l">'+l+'</span><span class="rep-ev-v">'+v+'</span></div>';}
 function sec(title,sub,rows){return '<h4 class="rep-ev-h">'+title+(sub?' <span class="rep-ev-sub">'+sub+'</span>':'')+'</h4>'+rows;}
 var bo=sec('Benefit Orders','',
   row('Orders closed (period)',ord)+
   row('New Plan — cancelled / fulfilled',ncn+' / '+npd+(ncd?' ('+(100*ncn/ncd).toFixed(1)+'% cancel)':''))+
   row('Renewal + Change — fulfilled',rnd)+
   row('BO Status (OA Held) — orders that met all entered OA stages',oad?oan+' / '+oad+' = '+(100*oan/oad).toFixed(1)+'%':'—'));
 var tk=sec('Tickets','Ful→OA · longest-held BO owner',
   row('Tickets closed in period',tsd)+
   row('Closed within 5 days',tsd?tsn+' / '+tsd+' = '+(100*tsn/tsd).toFixed(1)+'%':'—'));
 var cl=sec('Calls','',
   row('Eligible days (selected months)',avd)+
   row('SLA days met (avail 80–105%)',avd?avs+' / '+avd+' = '+(100*avs/avd).toFixed(1)+'%':'—')+
   row('Abandon (modified)',abd?abn+' / '+abd+' inbound = '+(100*abn/abd).toFixed(1)+'%':'—'));
 return '<div class="rep-section"><h3>Supporting detail</h3>'+bo+tk+cl+
   '<h4 class="rep-ev-trh">Ticket Rate — by order type</h4>'+repTicketBreak(r)+'</div>';}
function repMethodology(){return '<div class="rep-methodology"><h2>Methodology</h2>'+
 '<p style="color:var(--gt);font-size:12px">Period = your selected months. Closed = fulfilled or cancelled.</p>'+
 '<p><b>Avg Weighted Attainment</b> — the straight average of the three areas (SLA Delivery, Quality, Cancel), each weighted equally. Reflects delivered performance; floors do not affect it.</p>'+
 '<p><b>QPR Attainment</b> — the same average, but any metric below its floor resets its whole area to 0%. Used to inform the quarterly review. With one area gated, QPR cannot exceed ~83.3% (two areas gated → ~41.7%).</p>'+
 '<h3>Per-metric definitions</h3><div class="mdef-list">'+
  ORDER.map(function(k){return '<div class="mdef-item"><div class="mdef-h"><span class="mdef-nm">'+dirArrow(k)+' '+MLABEL[k].l+'</span><span class="mdef-gf">'+goalTxt(k)+' / '+floorTxt(k)+'</span></div><div class="mdef-d">'+MDEF[k]+'</div></div>';}).join('')+
  '</div>'+
 '<h3>Attribution &amp; small-N guards</h3><p style="color:var(--dk)">Orders, cancels and ticket-rate are attributed to the OA Benefit Order owner via the employee-ID bridge (handles name changes and migrations). Ticket SLA (Ful→OA tickets) is attributed to the OA Benefit Order owner via the same bridge. Ticket SLA needs ≥5 tickets in the period; Ticket Rate excludes any period with fewer than 5 fulfilled BOs (per order type); New Plan Cancel needs ≥10 New-Plan orders — below threshold the value is suppressed rather than shown.</p></div>';}
function renderReport(name){var a=DATA.ics.filter(function(i){return i.name===name})[0];if(!a)return '';
 var r=computeRow(a);var rows=cohortRows();
 var poolW=rows.filter(function(x){return x.weighted!=null}).map(function(x){return x.weighted}).sort(function(p,q){return q-p});
 var poolQ=rows.filter(function(x){return x.qpr!=null}).map(function(x){return x.qpr}).sort(function(p,q){return q-p});
 var ms=selMonths();var per=ms.length===DATA.months.length?DATA.period:ms.map(function(m){return ML[m]}).join(', ');
 var gen=new Date().toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'});
 var perF=ms.length<=1?(ms.length?ML[ms[0]]+' '+ms[0].slice(0,4):'—'):ML[ms[0]]+' '+ms[0].slice(0,4)+' – '+ML[ms[ms.length-1]]+' '+ms[ms.length-1].slice(0,4);
 var h='<div class="rep-header"><div class="rep-title">New Plan &amp; Renewal Onboarding — Performance Report</div><div class="rep-name">'+r.name+'</div><div class="rep-sub"><b>PE:</b> '+(r.pe||'—')+' · <b>Period:</b> '+per+' · <b>Orders closed:</b> '+r.nOrders+' · <b>Generated:</b> '+gen+'</div></div>';
 h+=repSummaryRow('Avg Weighted Attainment',r.weighted,'Straight average across the three areas. Always reflects delivered performance.',poolW);
 h+=repSummaryRow('QPR Attainment',r.qpr,'Same average; any area with a below-floor metric is set to 0%. With 3 areas, one gated area caps QPR at 83.3%.',poolQ);
 h+='<div class="rep-disclaimer"><b>How to read this:</b> the star marks where you fall on the team distribution for the selected period; the labeled bars are the 25th / 50th / 75th / 90th percentile attainment across the team. This reflects <b>everyone on the team</b> for the period — formal QPR ratings will typically <b>exclude ICs ineligible for a review</b> during the quarter, so the official review cohort can differ slightly. <b>Avg Weighted</b> reflects delivered performance; <b>QPR</b> zeroes any area with a metric below floor.</div>';
 h+='<div class="rep-section"><h3>Metric scorecard</h3><table class="rep-table"><thead><tr><th>Metric</th><th>Value</th><th>Goal</th><th>Floor</th><th class="r">Attainment</th><th>Status</th></tr></thead><tbody>'+repMetricRows(r)+'</tbody></table></div>';
 h+=repEvidence(r);
 h+=repDiag(r);
 h+=repMethodology();
 h+='<div class="rep-foot">Report for: <b>'+r.name+'</b> · PE: '+(r.pe||'—')+' · Period: '+perF+'<br>Generated: '+gen+'</div>';
 return h;}
function openReport(name){$('repBody').innerHTML=renderReport(name);$('repModal').classList.add('open');document.body.style.overflow='hidden';
 var ms=selMonths();var p=ms.length?(ms[0]+(ms.length>1?'_to_'+ms[ms.length-1]:'')):'all';document.title=name.replace(/[^A-Za-z0-9]+/g,'_')+'_Performance_'+p;}
function closeReport(){$('repModal').classList.remove('open');document.body.style.overflow='';document.title=ORIGINAL_TITLE;}

function ratingBucket(r){return r.rating==null?'none':(r.rating===1?'1':r.rating===2?'2':'3');}
function tableRows(){var rs=rowsComputed();if(ratingFilter!=null)rs=rs.filter(function(r){return ratingBucket(r)===String(ratingFilter);});return rs;}
function renderRatingDist(rows){var sec=$('histSection');var c1=0,c2=0,c3=0,c_=0;
 rows.forEach(function(r){if(r.rating==null)c_++;else if(r.rating===1)c1++;else if(r.rating===2)c2++;else c3++;});
 var bars=[{key:'1',count:c1,color:'r1',label:'1',sub:'BELOW FLOOR'},{key:'2',count:c2,color:'r2',label:'2',sub:'NO MISS, NOT TOP 15%'},{key:'3',count:c3,color:'r3',label:'3',sub:'TOP 15%'},{key:'none',count:c_,color:'rnone',label:'—',sub:'NO RATING'}];
 var mx=0;bars.forEach(function(b){if(b.count>mx)mx=b.count});if(mx===0)mx=1;
 var h='<div class="rd-card"><h3>Suggested QPR Rating Distribution <span class="tip">?<span class="tip-text">Ranked by QPR attainment. Rating 3 = top 15% with no floor miss; 2 = no floor miss, not top 15%; 1 = a metric below floor. Click a bar to filter the table; click again to clear.</span></span></h3>';
 h+='<div class="sub">'+rows.length+' IC'+(rows.length===1?'':'s')+' · dynamic against the visible filter set</div>';
 if(ratingFilter!=null){var fl=ratingFilter==='none'?'no rating':'Rating '+ratingFilter;h+='<div class="rd-filter-chip" id="rdClear">Filtered to '+fl+' <span class="x">✕</span></div>';}
 h+='<div class="rd-chart">';var barH=140;var hasSel=ratingFilter!=null;
 bars.forEach(function(b){var px=b.count>0?Math.max(Math.round(b.count/mx*barH),14):0;var empty=b.count===0;var sel=hasSel&&String(ratingFilter)===b.key;
   var cls='rd-bar-wrap'+(empty?' empty':'')+(hasSel&&!sel?' dim':'')+(sel?' sel':'');
   h+='<div class="'+cls+'" data-rate="'+b.key+'"><div class="rd-bar-ct">'+b.count+'</div><div class="rd-bar '+b.color+'" style="height:'+px+'px"></div><div class="rd-bar-lbl">'+b.label+'</div><div class="rd-bar-sublbl">'+b.sub+'</div></div>';});
 h+='</div>';
 if(c1+c2+c3===0)h+='<div class="rd-note">No rated ICs match the current filter.</div>';
 h+='</div>';sec.innerHTML=h;
 sec.querySelectorAll('.rd-bar-wrap').forEach(function(w){if(w.classList.contains('empty'))return;w.onclick=function(){var k=w.dataset.rate;ratingFilter=(ratingFilter===k)?null:k;renderViews();};});
 var clr=$('rdClear');if(clr)clr.onclick=function(){ratingFilter=null;renderViews();};}
function poolPE(rows){var ics=rows.map(function(r){return r.a});var months={};DATA.months.forEach(function(m){months[m]={}});ics.forEach(function(a){DATA.months.forEach(function(m){var am=a.months[m];if(am){for(var f in am){var v=+am[f];if(!isNaN(v))months[m][f]=(months[m][f]||0)+v;}}})});return computeRow({a:null,name:'(team)',manager:'(team)',team:'',months:months});}
function renderPE(){var rows=rowsComputed().filter(function(r){return r.weighted!=null});var _allP=poolPE(rows);var by={};rows.forEach(function(r){(by[r.pe]=by[r.pe]||[]).push(r)});
 var mean=function(a){return a.length?a.reduce(function(s,x){return s+x},0)/a.length:0};
 var R3=rows.filter(function(r){return r.rating===3}).length,R2=rows.filter(function(r){return r.rating===2}).length,R1=rows.filter(function(r){return r.rating===1}).length,tot=rows.length||1;
 $('peSummary').innerHTML='<div class="pe-stat"><div class="lbl">Mean Avg Weighted</div><div class="val" style="color:var(--teal)">'+(_allP.weighted==null?0:_allP.weighted).toFixed(1)+'%</div><div class="sub">weighted by team size</div></div>'+
   '<div class="pe-stat"><div class="lbl">Mean QPR Attainment</div><div class="val" style="color:var(--rd)">'+(_allP.qpr==null?0:_allP.qpr).toFixed(1)+'%</div><div class="sub">weighted by team size</div></div>'+
   '<div class="pe-stat"><div class="lbl">Suggested Rating 3</div><div class="val" style="color:var(--gn)">'+R3+' / '+tot+'</div><div class="sub">'+Math.round(100*R3/tot)+'% of filtered ICs</div></div>'+
   '<div class="pe-stat"><div class="lbl">Suggested Rating 2</div><div class="val" style="color:var(--amber)">'+R2+' / '+tot+'</div><div class="sub">'+Math.round(100*R2/tot)+'% of filtered ICs</div></div>'+
   '<div class="pe-stat"><div class="lbl">Suggested Rating 1</div><div class="val" style="color:var(--rd)">'+R1+' / '+tot+'</div><div class="sub">'+Math.round(100*R1/tot)+'% of filtered ICs</div></div>';
 var peScore={};Object.keys(by).forEach(function(pe){peScore[pe]=poolPE(by[pe])});var order=Object.keys(by).sort(function(a,b){return (peScore[b].qpr==null?-1:peScore[b].qpr)-(peScore[a].qpr==null?-1:peScore[a].qpr)});
 var h='<div class="pe-row"><div class="peg hd"><div></div><div>People Empowerer</div><div>Avg Weighted</div><div>QPR Attainment</div><div>Suggested Rating Distribution (3 / 2 / 1)</div><div>CSAT<span class="pe-csub">avg 1–5 · n</span></div><div>Email SLA<span class="pe-csub">% met ≤4hr SLA</span></div><div>Maestro<span class="pe-csub">% eligible orders, all tasks done</span></div></div></div>';
 order.forEach(function(pe){var t=by[pe];var pr=peScore[pe];var tt=t.length||1;var r3=t.filter(function(r){return r.rating===3}).length,r2=t.filter(function(r){return r.rating===2}).length,r1=t.filter(function(r){return r.rating===1}).length;var tcs=teamDiag(t,'csat'),tem=teamDiag(t,'email_sla'),tma=teamDiag(t,'maestro');var csN=0,emMet=0,emTot=0,maMet=0,maTot=0;t.forEach(function(rr){selMonths().forEach(function(m){csN+=rr.a.months[m].cs_n||0;emMet+=rr.a.months[m].em_n||0;emTot+=rr.a.months[m].em_d||0;maMet+=rr.a.months[m].ma_n||0;maTot+=rr.a.months[m].ma_d||0;});});
   h+='<div class="pe-row '+(state.peOpen[pe]?'open':'')+'"><div class="peg pe-click" data-pe="'+pe+'"><div class="caret">▸</div>'+
     '<div class="pe-nm">'+pe+'<span class="s">'+t.length+' ICs</span></div>'+
     '<div class="pe-num" style="color:'+bandColor(pr.weighted)+'">'+(pr.weighted==null?0:pr.weighted).toFixed(1)+'%</div>'+
     '<div class="pe-num" style="color:'+bandColor(pr.qpr)+'">'+(pr.qpr==null?0:pr.qpr).toFixed(1)+'%</div>'+
     '<div><div class="pe-rdist"><div class="seg s3" style="width:'+(100*r3/tt)+'%"></div><div class="seg s2" style="width:'+(100*r2/tt)+'%"></div><div class="seg s1" style="width:'+(100*r1/tt)+'%"></div></div><div class="pe-rdist-cap"><b>'+r3+'</b> rated 3 · <b>'+r2+'</b> rated 2 · <b>'+r1+'</b> rated 1</div></div>'+'<div class="pe-diag" style="color:'+diagBand('csat',tcs)+'">'+(tcs==null?'—':tcs.toFixed(2))+'<span class="s">'+(csN>0?'n='+csN:'')+'</span></div>'+'<div class="pe-diag" style="color:'+diagBand('email_sla',tem)+'">'+(tem==null?'—':tem.toFixed(0)+'%')+'<span class="s">'+(emTot>0?emMet+' / '+emTot:'')+'</span></div>'+'<div class="pe-diag" style="color:'+diagBand('maestro',tma)+'">'+(tma==null?'—':tma.toFixed(0)+'%')+'<span class="s">'+(maTot>0?maMet+' / '+maTot:'')+'</span></div>'+'</div>'+
     '<div class="pe-drill '+(state.peOpen[pe]?'open':'')+'"><table style="width:100%"><thead><tr><th>IC</th>'+ORDER.map(function(k){return '<th class="r">'+(MLABEL[k].short||MLABEL[k].l)+'</th>';}).join('')+'<th class="r">WTD</th><th class="r">QPR</th></tr></thead><tbody>'+
       t.slice().sort(function(a,b){return b.qpr-a.qpr}).map(function(r){
         return '<tr><td class="nm pe-ic-link" data-ic="'+r.name+'">'+r.name+'</td>'+ORDER.map(function(k){return cell(k,r.m[k]);}).join('')+scoreCell(r.weighted,'r')+scoreCell(r.qpr,'r')+'</tr>';}).join('')+
       (function(){var PB=poolPE(t);return '<tr class="pe-blend" style="border-top:2px solid #cfcfcf;font-weight:600"><td class="nm">TEAM BLENDED <span class="muted">'+t.length+' IC'+(t.length===1?'':'s')+'</span></td>'+ORDER.map(function(k){return cell(k,PB.m[k]);}).join('')+scoreCell(PB.weighted,'r')+scoreCell(PB.qpr,'r')+'</tr>';})()+
     '</tbody></table></div></div>';});
 $('peRows').innerHTML=h;}

var SAMPLES=[
 {t:'Strong performance on all targets',n:'Sample A',tone:'great',rating:3,v:{phone_avail:92,abandon:2.5,ticket_sla:88,oa_held:85,qa:95,ticket_np:1.0,ticket_rn:0.30,np_cancel:10}},
 {t:'Strong performance with some opportunity',n:'Sample B',tone:'mid',rating:2,v:{phone_avail:80,abandon:5,ticket_sla:70,oa_held:70,qa:91,ticket_np:1.25,ticket_rn:0.40,np_cancel:15}},
 {t:'Moderate performance with some opportunity',n:'Sample C',tone:'mid',rating:2,v:{phone_avail:68,abandon:5,ticket_sla:65,oa_held:60,qa:88,ticket_np:1.45,ticket_rn:0.45,np_cancel:18}},
 {t:'Low performance with metric below floor',n:'Sample D',tone:'low',rating:1,v:{phone_avail:55,abandon:12,ticket_sla:55,oa_held:40,qa:80,ticket_np:1.7,ticket_rn:0.55,np_cancel:30}}];
function exCard(s){var sc=scoreVals(function(k){return s.v[k]},function(){return{np:s.v.ticket_np,rn:s.v.ticket_rn,npd:50,rnd:50};});var cls=s.tone;
 var body=AREAS.map(function(a){var aa=sc.area[a.k];var miss=areaMiss({m:sc.m},a);var bcol=miss?'var(--rd-bg)':aa>=100?'var(--gn-bg)':aa>=80?'var(--am-bg)':'var(--rd-bg)';
   return '<div class="ex-area-wrap"><div class="ex-bucket-label" style="color:'+a.c+'">'+a.l+' Area</div>'+
     a.metrics.map(function(k){var c=sc.m[k];var bf=c.status==='miss';return '<div class="ex-row'+(bf?' below-floor':'')+'"><span class="ex-l">'+MLABEL[k].l+'</span><span class="ex-v">'+valText(k,c)+'</span><span class="ex-att">'+(c.att==null?'—':c.att.toFixed(0)+'% att')+'</span></div>';}).join('')+
     '<div class="ex-bucket-score" style="background:'+bcol+'"><span>'+a.l+' Score</span><span class="bv">'+(aa==null?'—':aa.toFixed(1)+'%')+(miss?' → 0% (QPR)':'')+'</span></div></div>';}).join('');
 return '<div class="ex-card '+cls+'"><h4>'+s.t+'</h4><div class="ex-name">'+s.n+'</div>'+body+
   '<div class="ex-dual"><div class="ex-dual-cell"><span class="l">Avg Weighted</span><span class="v" style="color:'+bandColor(sc.weighted)+'">'+sc.weighted.toFixed(1)+'%</span></div><div class="ex-dual-cell"><span class="l">QPR</span><span class="v" style="color:'+bandColor(sc.qpr)+'">'+sc.qpr.toFixed(1)+'%</span></div><div class="ex-dual-cell"><span class="l">Suggested Rating</span><span class="v"><span class="rate-chip r'+s.rating+'">'+s.rating+'</span></span></div></div></div>';}

function renderCalc(){
 var aw=Math.round(100/AREAS.length);
 var top=AREAS.map(function(a){return '<div class="wt-area" style="background:'+a.c+'22;color:'+a.c+';flex:1">'+a.l+' — '+aw+'%</div>';}).join('');
 var bot=AREAS.map(function(a){var ws=areaWsum(a);return a.metrics.map(function(k){var per=aw*WREL[k]/ws;return '<div class="wt-seg" style="background:'+a.c+';flex:'+(WREL[k]/ws)+'"><span>'+MLABEL[k].short+'</span><span class="w">'+per.toFixed(per<10?1:0)+'%</span></div>';}).join('');}).join('');
 var slaA=AREAS[0].metrics.map(function(k){return MLABEL[k].short+' att'}).join(', ');
 var wsQ=areaWsum(AREAS[1]);
 var qA=AREAS[1].metrics.map(function(k){return MLABEL[k].short+'×'+Math.round(WREL[k]/wsQ*100)+'%'}).join(' + ');
 var rowsT=ORDER.map(function(k){var m=MLABEL[k],a=AREAOF[k];var per=(aw*WREL[k]/areaWsum(a));
   var calc=MDEF[k];
   return '<tr><td class="mn">'+m.l+'</td><td><span class="bucket" style="background:'+a.c+'">'+a.l.split(' ')[0]+'</span></td><td>'+calc+'</td><td class="r">'+goalTxt(k)+'</td><td class="r">'+floorTxt(k)+'</td><td class="r">'+per.toFixed(per<10?1:0)+'%</td></tr>';}).join('');
 $('tab-calc').innerHTML=
 '<div class="card"><h2>How attainment is calculated</h2><div class="calc-prose">'+
  '<p>Each IC is measured across <b>seven metrics</b>, grouped into three areas: <b class="em">SLA Delivery</b> (Phone Availability, Abandon, Ticket SLA, BO Status (OA Held)), <b class="em">Quality</b> (Level AI QA, Ticket Rate), and <b class="em">Cancel</b> (New Plan Cancel Rate). The three areas count <b>equally</b> toward the total. Within SLA Delivery and Cancel the metrics carry equal weight; within Quality, <b>Level AI QA is weighted half and Ticket Rate the other half</b>. Ticket Rate is a single metric with separate New Plan and Renewal+Change targets, blended by volume.</p>'+
  '<p>Every metric has a <b class="em">target</b> (where we want everyone to be) and a <b class="em">floor</b> (the minimum expectation). Two scores are reported for each IC.</p>'+
  '<p><b>Avg Weighted Attainment</b> is the average across the seven metrics. It always reflects delivered performance, regardless of where any individual metric lands. <b>QPR Attainment</b> uses the same average, but if any metric is below its floor, the <b>entire area it belongs to resets to zero</b>. This is the score used in the quarterly performance review. When one area is zeroed out, the QPR cannot go above approximately <b>83.3%</b> (two areas zeroed → ~41.7%).</p></div>'+
  '<div class="wt-bar">'+top+'</div><div class="wt-bar2">'+bot+'</div><div class="wt-cap">Top tier: equal 3-area split · Bottom tier: equal split within each area</div>'+
  '<div class="fbox" style="margin-top:14px"><span class="em">SLA score</span> = avg('+slaA+')<br><span class="em">Quality score</span> = '+qA+'<br><span class="em">Cancel score</span> = NP Cancel att<br><span class="cm">// Each per-metric attainment = min(actual / goal × 100, 125)</span><br><span class="em">Avg Weighted</span> = (SLA × 33%) + (Quality × 33%) + (Cancel × 33%)<br><span class="emr">QPR</span> = same formula, but an area score is set to <span class="emr">0%</span> if any of its metrics is below the floor</div>'+
  '<div class="concept-grid"><div class="concept"><h4>Per-metric attainment</h4><p>How a metric scores against its target. For most metrics: <code>actual ÷ target × 100</code>. For Abandon, Cancel and Ticket Rate (lower is better): <code>target ÷ actual</code>.</p></div>'+
   '<div class="concept"><h4>Floor</h4><p>The minimum expectation for a metric. If any metric is below its floor, its <b>area</b> counts as 0% in QPR Attainment. Avg Weighted is unaffected.</p></div>'+
   '<div class="concept"><h4>125% cap</h4><p>No metric scores above 125%, so one strong result doesn\'t mask weaker ones elsewhere.</p></div>'+
   '<div class="concept"><h4>Min volume</h4><p>Ticket SLA needs ≥5 tickets in the period. Ticket Rate excludes any period with &lt;5 fulfilled BOs (checked separately for New Plan and Renewal+Change). New Plan Cancel needs ≥10 New-Plan orders. Below threshold, the value is suppressed instead of shown.</p></div><div class="concept"><h4>Suggested Rating</h4><p><b>3 / 2 / 1</b>, recomputed against the visible filtered set. <b>3</b> = top 15% (round up) by QPR of the no-floor-miss pool · <b>2</b> = no floor miss, not top 15% · <b>1</b> = ≥1 metric below floor. Suggestion only — the final rating also reflects diagnostic/supporting measures, AI ratings, and behaviors aligned with Gusto values.</p></div></div></div>'+
 '<div class="card"><h2>The metrics</h2><table class="exp-tbl"><thead><tr><th>Metric</th><th>Bucket</th><th>Calculation</th><th class="r">Goal</th><th class="r">Floor</th><th class="r">Weight</th></tr></thead><tbody>'+rowsT+'</tbody></table></div>'+
 '<div class="card"><h2>Diagnostic measures <span class="note">context only — not scored</span></h2><p class="muted" style="font-size:12px;margin-bottom:10px">Shown alongside the scorecard for context. <b>Not</b> part of Avg Weighted or QPR, and they do not affect the suggested rating.</p><table class="exp-tbl"><thead><tr><th>Measure</th><th>What it measures</th><th>Attribution</th></tr></thead><tbody>'+
  '<tr><td class="mn">CSAT</td><td>Customer satisfaction score (1–5) after case resolution.</td><td>Benefit-order owner (New Plan + Renewal)</td></tr>'+
  '<tr><td class="mn">Email SLA</td><td>% of inbound emails responded to within 4 business hours (HOOP).</td><td>BO owner at time of touchpoint</td></tr>'+
  '<tr><td class="mn">Maestro Adherence</td><td>Of Maestro-eligible benefit orders that entered RFSP in the month, the % with all Maestro tasks complete.</td><td>BO owner · bucketed by RFSP-entry month</td></tr>'+
  '</tbody></table></div>'+
 '<div class="card"><h2>BO Status (OA Held) — OA Held Status with Benefit Orders</h2><p class="muted" style="font-size:12px;margin-bottom:8px">An order is "OA-held" when it met the ≤1-day SLA on <b>every</b> gustie-controlled OA stage it passed through (consecutive re-entries within a day are merged into one stint, matching the Benefit Order SLA model). <b>Denominator = all CLOSED orders (fulfilled + cancelled, including Change) that entered at least one of the stages below</b>; cancelled orders count, and orders that never entered an OA stage are excluded — consistent with the Benefit Order & Advising SLA dashboards:</p><span class="day-badge">Ready for OE Prep ≤1d</span><span class="day-badge">OE Verification ≤1d</span><span class="day-badge">ER Outreach Required ≤1d</span><span class="day-badge">Awaiting Routing ≤1d</span><span class="day-badge">Approved ≤1d</span></div>'+
 '<div class="card"><h2>Worked examples <span class="note">illustrative</span></h2><p class="muted" style="font-size:12px;margin-bottom:10px">Four scenarios showing how the formula plays out across both attainment views.</p><div class="examples-grid">'+SAMPLES.map(exCard).join('')+'</div></div>';}

function renderResources(){var root=$('tab-resources');if(!root||root.__wired)return;root.__wired=true;
 root.querySelectorAll('.dr-h').forEach(function(h){h.addEventListener('click',function(){h.closest('.dr-card').classList.toggle('open');});});
 root.querySelectorAll('.dr-copy').forEach(function(b){b.addEventListener('click',function(e){e.stopPropagation();var code=b.closest('.dr-codewrap').querySelector('pre').innerText;navigator.clipboard.writeText(code).then(function(){var t=b.textContent;b.textContent='Copied ✓';setTimeout(function(){b.textContent=t;},1200);});});});}

function ddMulti(id,label,sub,opts,sel,allLabel){var n=(!sel.length||sel.length===opts.length)?allLabel:(id==='adv'?sel.length+' of '+opts.length+' ICs':sel.length+' selected');
 return '<div class="fg"><label>'+label+'</label><button class="fbtn" data-dd="'+id+'">'+n+' <span class="arr">▾</span></button><div class="flab">'+sub+'</div>'+
  '<div class="dd" id="dd-'+id+'"><div class="ddtop"><button data-all="'+id+'">All</button><button data-none="'+id+'">None</button></div>'+
  (opts.length>5?'<div class="dd-search"><input type="text" placeholder="Search…" data-search="'+id+'"></div>':'')+
  opts.map(function(o){return '<label><input type="checkbox" data-opt="'+id+'" value="'+o+'" '+(!sel.length||sel.indexOf(o)>=0?'checked':'')+'>'+(id==='months'?ML[o]:o)+'</label>';}).join('')+'</div></div>';}
function renderFilters(){
 var pes=Array.from(new Set(DATA.ics.map(function(i){return i.manager}))).filter(Boolean).sort();
 var advs=Array.from(new Set(DATA.ics.map(function(i){return i.name}))).sort();
 $('filterbar').innerHTML=
   ddMulti('months','Months','Applies to all metrics',DATA.months,state.months.length===DATA.months.length?[]:state.months,'All Months')+
   ddMulti('pe','PE','Multi-select',pes,state.pe,'All PEs')+
   ddMulti('adv','IC','No-data ICs unchecked by default',advs,state.adv,advs.length+' ICs');
 document.querySelectorAll('[data-dd]').forEach(function(b){b.onclick=function(e){e.stopPropagation();var dd=$('dd-'+b.dataset.dd);var op=dd.classList.contains('open');document.querySelectorAll('.dd').forEach(function(d){d.classList.remove('open')});if(!op)dd.classList.add('open');};});
 document.querySelectorAll('.dd').forEach(function(d){d.onclick=function(e){e.stopPropagation();};});
 document.querySelectorAll('[data-search]').forEach(function(inp){inp.onclick=function(e){e.stopPropagation();};inp.oninput=function(){var q=inp.value.toLowerCase();$('dd-'+inp.dataset.search).querySelectorAll('label').forEach(function(l){l.style.display=(q===''||l.textContent.toLowerCase().indexOf(q)>=0)?'':'none';});};});
 function collect(id){var all=Array.from(document.querySelectorAll('[data-opt="'+id+'"]'));var sel=all.filter(function(x){return x.checked}).map(function(x){return x.value});return{sel:sel,all:all.length};}
 document.querySelectorAll('[data-opt]').forEach(function(c){c.onchange=function(){var id=c.dataset.opt;var r=collect(id);
   if(id==='months'){state.months=r.sel.length?r.sel:['~'];autoAdv();}
   if(id==='pe')state.pe=r.sel.length===r.all?[]:r.sel;
   if(id==='adv')state.adv=r.sel.length===r.all?[]:r.sel;renderViews();};});
 document.querySelectorAll('[data-all]').forEach(function(b){b.onclick=function(){var id=b.dataset.all;document.querySelectorAll('[data-opt="'+id+'"]').forEach(function(x){x.checked=true});if(id==='months')state.months=DATA.months.slice();if(id==='pe')state.pe=[];if(id==='adv')state.adv=[];renderViews();};});
 document.querySelectorAll('[data-none]').forEach(function(b){b.onclick=function(){var id=b.dataset.none;document.querySelectorAll('[data-opt="'+id+'"]').forEach(function(x){x.checked=false});if(id==='months')state.months=['~'];if(id==='pe')state.pe=['~'];if(id==='adv')state.adv=['~'];renderViews();};});}

function ddLabel(id){if(id==='months'){if(state.months.length===1&&state.months[0]==='~')return 'None';var n=state.months.length;return (n===0||n===DATA.months.length)?'All Months':n+' selected';}if(id==='pe'){if(state.pe.length===0)return 'All PEs';if(state.pe.length===1&&state.pe[0]==='~')return 'None';return state.pe.length+' selected';}var tot=Array.from(new Set(DATA.ics.map(function(i){return i.name}))).length;if(state.adv.length===0)return tot+' ICs';if(state.adv.length===1&&state.adv[0]==='~')return 'None';return state.adv.length+' of '+tot+' ICs';}
function updFilterLabels(){['months','pe','adv'].forEach(function(id){var b=document.querySelector('[data-dd="'+id+'"]');if(b)b.innerHTML=ddLabel(id)+' <span class="arr">▾</span>';});}
function renderViews(){var rows=rowsComputed();renderKPIs(rows);renderRatingDist(rows);renderTbl(tableRows());renderPE();updFilterLabels();
 $('foot').innerHTML='<div class="calc-footer" style="flex-direction:row;align-items:center;justify-content:flex-start;flex-wrap:wrap;gap:6px 18px"><span><b>Data updated as of</b> · '+(DATA.data_through||DATA.published||'')+'</span><span><b>Last published</b> · '+DATA.published+'</span><span style="margin-left:auto"><b>Questions?</b> Contact Rehana Manejwala and Lee Ann Volosin</span></div>';}
function renderAll(){renderFilters();renderViews();renderCalc();renderResources();}

// auto-uncheck ICs with no scored metric in the selected month(s); month-aware (re-derives on month change)
function autoAdv(){var all=DATA.ics.map(function(i){return i.name});var hd=DATA.ics.filter(function(a){return computeRow(a).weighted!=null}).map(function(a){return a.name});state.adv=(hd.length&&hd.length<all.length)?hd:[];}
autoAdv();

document.addEventListener('click',function(){document.querySelectorAll('.dd').forEach(function(d){d.classList.remove('open')});});
document.querySelectorAll('.tab-btn').forEach(function(b){b.onclick=function(){document.querySelectorAll('.tab-btn').forEach(function(x){x.classList.remove('on')});b.classList.add('on');state.tab=b.dataset.tab;document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on')});$('tab-'+state.tab).classList.add('on');};});
$('sb').oninput=function(){state.q=this.value.trim();renderTbl(tableRows());};
$('icTbl').addEventListener('click',function(e){
 var cta=e.target.closest('[data-cl]');if(cta){e.stopPropagation();var ak=cta.dataset.cl;state.collapsed[ak]=!state.collapsed[ak];renderTbl(tableRows());return;}
 var th=e.target.closest('th');if(th&&th.dataset.k){if(state.sort===th.dataset.k)state.dir*=-1;else{state.sort=th.dataset.k;state.dir=-1;}renderTbl(tableRows());return;}
 var tr=e.target.closest('tr.dat');if(tr){openReport(tr.dataset.ic);}});
$('peRows').addEventListener('click',function(e){var ic=e.target.closest('[data-ic]');if(ic){e.stopPropagation();openReport(ic.dataset.ic);return;}var c=e.target.closest('[data-pe]');if(!c)return;var pe=c.dataset.pe;state.peOpen[pe]=!state.peOpen[pe];renderPE();});
$('repClose').onclick=closeReport;$('repOverlay').onclick=closeReport;$('repPrint').onclick=function(){window.print();};
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeReport();});
renderAll();
'''

BODY='''<body><div class="wrap">
<div class="hdr"><h1>New Plan and Renewal Onboarding — Performance Dashboard</h1></div>
<div class="tabs">
 <button class="tab-btn on" data-tab="performance">Performance</button>
 <button class="tab-btn" data-tab="pe">PE Attainment</button>
 <button class="tab-btn" data-tab="calc">Attainment Calculation</button>
 <button class="tab-btn" data-tab="resources">Data Resources</button>
</div>
<div class="fb" id="filterbar"></div>
<div class="tab on" id="tab-performance">
 <div class="kpis" id="kpis"></div>
 <div id="histSection"></div>
 <div class="card"><h2>Per-IC attainment <span class="tip">?<span class="tip-text">Click any IC for the full scorecard. ✓ at/above goal · ⚠ between floor &amp; goal · ✗ below floor. Click a header to sort; expand an area for its metrics.</span></span></h2>
  <div class="tbl-toolbar"><div class="lg"><span><b class="s ico-g" style="font-family:var(--ft)">✓</b> at or above goal</span><span><b class="s" style="color:var(--amber)">⚠</b> between floor &amp; goal</span><span><b class="s" style="color:var(--rd)">✗</b> below floor (gate fail)</span><span><b class="s muted">—</b> no data</span></div><input class="sb" id="sb" placeholder="Search IC or PE…"></div>
  <div class="tbl-wrap"><table id="icTbl"><thead></thead><tbody></tbody></table></div></div>
</div>
<div class="tab" id="tab-pe"><div class="card"><h2>PE Attainment</h2><p class="pe-explain">This view rolls each IC\\'s individual attainment up to their <b>People Empowerer (PE)</b>. Use the <span class="em">Months</span>, <span class="em">PE</span>, and <span class="em">IC</span> filters above to narrow the view. Each PE row shows <b>team size</b>, <b>Avg Weighted</b>, <b>QPR Attainment</b>, the <b>Suggested Rating distribution</b> (3 / 2 / 1), and team <b>CSAT</b> &amp; <b>Email SLA</b>. Click any PE row to expand.</p><div class="pe-summary-row" id="peSummary"></div><div id="peRows"></div></div></div>
<div class="tab" id="tab-calc"></div>
<div class="tab" id="tab-resources">__RESHTML__</div>
<div id="foot"></div>
</div>
<div class="rep-modal" id="repModal"><div class="rep-overlay" id="repOverlay"></div><div class="rep-shell"><div class="rep-actions"><button class="rep-btn primary" id="repPrint">Save as PDF</button><button class="rep-btn" id="repClose">Close</button></div><div class="rep-body" id="repBody"></div></div></div>
<script>__JS__</script></body></html>'''

HTML='<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>New Plan &amp; Renewal Onboarding — Performance</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;500;600;700;800&display=swap" rel="stylesheet"><link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'+CSS+'</head>'+BODY.replace('__RESHTML__',RES_HTML).replace('__JS__',JS.replace('__DATA__',DATA_JSON))
# ── New-hire default-off: force newly-hired ICs unchecked by default (persists across refreshes) ──
import sys as _sys, os as _os
_ROOT=_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0,_ROOT)
import new_hire_off as _nho
HTML=_nho.apply(HTML,"npr",_os.path.join(_ROOT,"new_hire_default_off.json"))
open('np_renewal_onboarding_performance_dashboard_v6.html','w').write(HTML)
print('wrote',len(HTML),'bytes')
