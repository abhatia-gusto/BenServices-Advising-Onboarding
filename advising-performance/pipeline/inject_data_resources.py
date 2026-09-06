#!/usr/bin/env python3
"""Rebuild the Advising Performance dashboard's "Data Resources" tab (#tab-rawdata)
from the canonical query files, in place.

Content: a hero link to the single source-dashboard hub (advising-onboarding-dashboards)
+ the component queries grouped by category, each showing main table / joins / grain /
params and the FULL query (Copy grabs the complete SQL).

Preserves the calc-footer (perfDT / perfRE date spans) that follows the tab card.
Idempotent: replaces only the <div class="card">…</div> inside #tab-rawdata.
"""
import os, re, html, pathlib

HERE = pathlib.Path(__file__).parent
V11 = HERE / "advising_performance_dashboard_v11.html"

# ---- extract the two inline period queries from pull_v11_period_data.py ----
def extract_inline(funcname):
    src = (HERE / "pull_v11_period_data.py").read_text()
    m = re.search(r"def "+funcname+r"\(.*?\):(.*?)(?=\ndef |\Z)", src, re.S)
    q = re.search(r'sql\s*=\s*f?"""(.*?)"""', m.group(1), re.S)
    import textwrap
    t = textwrap.dedent(q.group(1)).strip()
    return t.replace("{WIN_START}", "{{start_date}}").replace("{WIN_END}", "{{end_date}}")

CALLS_SQL = extract_inline("pull_calls_per_month")
LAI_CH_SQL = extract_inline("pull_levelai_channels_per_month")

PE_SQL = ("select owner_name as advisor,\n"
          "       max_by(coalesce(pe_name, pe_name_at_close), close_date_computed) as pe\n"
          "from ( /* advising_opp_sla_v6_0.sql */ )\n"
          "where owner_name is not null\n"
          "group by 1;")

def rd(rel):
    return (HERE / rel).read_text().rstrip()

# segment: (id, title, category, sql_text, main, joins[], grain, params)
SEG = [
 ("opp_sla","Opportunity SLA — ER Confirm & RFD/Alt","SLA", rd("queries/advising_opp_sla_v6_0.sql"),
  "bi_reporting.advising_opportunities", ["bi.sfdc_opportunity_history"],
  "one row per opportunity","{{date_start}} / {{date_end}}"),
 ("ticket_sla","Ticket SLA (by flow)","SLA", rd("queries/ticket_sla_by_flow_v3.sql"),
  "bi.sfdc_tickets", ["bi.sfdc_users_gusto_employees_view","bi.gusto_employees","bi_reporting.advising_opportunities","bi_reporting.benefit_orders"],
  "one row per ticket","{{date_start}} / {{date_end}}"),
 ("bo_grain","Benefit Order Grain — fulfilled / cancelled / ticket rate","SLA", rd("queries/bo_grain_sla_v11.sql"),
  "bi_reporting.benefit_orders", ["bi.benefit_order_status_change_history","bi.gusto_employees","bi.sfdc_users_gusto_employees_view","bi.sfdc_opportunities_fact","bi.sfdc_tickets","bi_reporting.advising_opportunities"],
  "one row per benefit order","{{date_start}} / {{date_end}}"),
 ("availability","Phone Availability","SLA", rd("queries/av_pit_icmonth.sql"),
  "bi.gusto_employees (point-in-time roster)", ["bi.people_analytics_workday_time_tracking","bi.wfm_agent_activity_log_details"],
  "one row per team × name × month","{{start_date}} / {{end_date}}"),
 ("abandon","Phone Abandon (modified)","SLA", rd("queries/calls_pit_icmonth.sql"),
  "bi.phone_calls", ["bi.phone_user_metrics","bi.gusto_employees"],
  "one row per team × name × month","{{start_date}} / {{end_date}}"),
 ("email_sla","Email SLA","SLA", rd("email-sla-dashboard-source-attp.sql"),
  "bi.benefit_order_touchpoints", ["bi.cases","bi.gusto_employees","bi.sfdc_users_gusto_employees_view","bi.benefit_orders","bi.benefit_order_status_change_history","bi.sfdc_opportunity_history","bi_reporting.advising_opportunities","bi.static_calendar"],
  "one row per inbound email touchpoint","{{ TP Date Range Start }} / {{ TP Date Range End }}"),
 ("level_ai_qa","Level AI — QA score","Level AI", rd("queries/level_ai_qa.sql"),
  "bi.fct_level_ai_conversation_asr_log", ["bi.cases","bi.gusto_employees"],
  "one row per QA-scored conversation","{{start_date}} / {{end_date}}"),
 ("level_ai_channels","Level AI — Channels (call vs email)","Level AI", LAI_CH_SQL,
  "bi.fct_level_ai_conversation_asr_log", ["bi.cases","bi.gusto_employees"],
  "one row per QA-scored conversation → advisor × month × channel","{{start_date}} / {{end_date}}"),
 ("csat","CSAT","Quality", rd("queries/benops_csat_surveys.sql"),
  "bi_reporting.ces_csat_data", ["bi_reporting.benefit_orders","bi_reporting.advising_opportunities","bi.sfdc_opportunities_fact","bi.int_sfdc_user_current_gusto_employees_pepe"],
  "one row per survey","{{Date Start}} / {{Date End}}"),
 ("inapp","In-App Sentiment","Quality", rd("queries/benops_inapp_sentiment.sql"),
  "bi.application_survey_data", ["bi.user_roles","bi_reporting.advising_opportunities","bi.sfdc_opportunities_fact","bi.int_sfdc_user_current_gusto_employees_pepe"],
  "one row per survey","{{survey_start_date}} / {{survey_end_date}}"),
 ("phone_calls","Phone Calls / month","Phone", CALLS_SQL,
  "bi.phone_user_metrics", ["bi.gusto_employees"],
  "advisor × month (aggregated)","{{start_date}} / {{end_date}}"),
 ("pe_map","PE map (current PE per IC)","Roster / PE", PE_SQL,
  "bi_reporting.advising_opportunities (derived from opp SLA)", ["bi.sfdc_opportunity_history"],
  "one row per advisor","{{date_start}} / {{date_end}}"),
]

HUB_URL = "https://share-some-html.staging.zp-int.com/advising-onboarding-dashboards"
HUB = [
 ("SLA", [
   ("Benefit Order SLA","https://share-some-html.staging.zp-int.com/bo-sla-dashboard",""),
   ("Advising SLA","https://share-some-html.staging.zp-int.com/advising-sla-dashboard",""),
   ("Broker Onboarding SLA","https://share-some-html.staging.zp-int.com/broker-onboarding-sla-dashboard",""),
   ("Ticket SLA by Flow","https://share-some-html.staging.zp-int.com/ticket-sla-by-flow",""),
   ("Email SLA","https://share-some-html.staging.zp-int.com/benefit-services-email-sla",""),
   ("Phone Dashboard","https://share-some-html.staging.zp-int.com/advising-onboarding-phone",""),
 ]),
 ("Performance", [
   ("Advising Performance","https://share-some-html.staging.zp-int.com/advising-performance-dashboard","PW"),
   ("Advising Net MRR","https://share-some-html.staging.zp-int.com/advising-mrr-dashboard",""),
   ("Level Funded","https://share-some-html.staging.zp-int.com/benefit-services-level-funded-conversion","Cohort"),
   ("Key NPR Operating","https://share-some-html.staging.zp-int.com/key-npr-operating-metrics-cohort","Cohort"),
   ("NPR Team Performance","https://share-some-html.staging.zp-int.com/npr-onboarding-performance","Beta"),
   ("Broker Team Performance","https://share-some-html.staging.zp-int.com/broker-onboarding-performance","Beta"),
 ]),
 ("Quality", [
   ("Level AI Query","https://redash.zp-int.com/queries/156897","Redash"),
 ]),
 ("Customer Experience", [
   ("BenOps CSAT + In-App","https://share-some-html.staging.zp-int.com/benefit-services-csat-dashboard",""),
 ]),
]

def esc(s): return html.escape(s, quote=True)

def build_inner():
    css = """
<style>
  #tab-rawdata .drx{max-width:1000px}
  #tab-rawdata .dr-hub{background:linear-gradient(180deg,#ffffff,#f6fbf7);border:1px solid var(--ln,#e6ded2);
    border-left:5px solid var(--teal,#2f7d4f);border-radius:12px;padding:18px 20px;margin:6px 0 6px;}
  #tab-rawdata .dr-ey{font-size:11.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--teal,#1f5c39)}
  #tab-rawdata .dr-hub h3{margin:4px 0 2px;font-size:18px}
  #tab-rawdata .dr-url{font-size:13px;color:var(--teal,#2f7d4f);word-break:break-all}
  #tab-rawdata .dr-btn{display:inline-block;margin-top:10px;background:var(--teal,#2f7d4f);color:#fff;text-decoration:none;
    font-weight:700;font-size:13px;padding:9px 16px;border-radius:8px}
  #tab-rawdata .dr-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:14px 0 2px}
  #tab-rawdata .dr-col h4{font-size:11.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--teal,#1f5c39);
    margin:0 0 6px;border-bottom:2px solid var(--ln,#e6ded2);padding-bottom:4px}
  #tab-rawdata .dr-col a{display:block;font-size:12.5px;color:var(--dk,#1f2a24);text-decoration:none;padding:3px 0}
  #tab-rawdata .dr-col a:hover{text-decoration:underline}
  #tab-rawdata .dr-tag{font-size:9.5px;color:#6b7a72;border:1px solid var(--ln,#e6ded2);border-radius:5px;padding:0 4px;margin-left:4px}
  #tab-rawdata .dr-note{color:#6b7a72;font-size:12.5px;margin-top:10px}
  #tab-rawdata .dr-cat{font-size:13px;font-weight:800;color:var(--teal,#1f5c39);letter-spacing:.09em;text-transform:uppercase;
    margin:22px 0 6px;padding-bottom:6px;border-bottom:2px solid var(--ln,#e6ded2)}
  #tab-rawdata .dr-card{background:#fff;border:1px solid var(--ln,#e6ded2);border-left:4px solid var(--teal,#2f7d4f);
    border-radius:10px;margin:9px 0;overflow:hidden}
  #tab-rawdata .dr-h{display:flex;align-items:center;gap:12px;padding:12px 15px;cursor:pointer;user-select:none}
  #tab-rawdata .dr-h:hover{background:#fbfdfb}
  #tab-rawdata .dr-name{font-weight:700;font-size:14.5px}
  #tab-rawdata .dr-car{margin-left:auto;transition:transform .15s;color:#6b7a72;font-size:12px}
  #tab-rawdata .dr-card.open .dr-car{transform:rotate(90deg)}
  #tab-rawdata .dr-b{display:none;border-top:1px solid var(--ln,#e6ded2);padding:6px 15px 15px}
  #tab-rawdata .dr-card.open .dr-b{display:block}
  #tab-rawdata .dr-dl{display:grid;grid-template-columns:120px 1fr;gap:4px 14px;margin:11px 2px 12px;font-size:13px}
  #tab-rawdata .dr-dl dt{color:#6b7a72;font-weight:600}
  #tab-rawdata .dr-dl dd{margin:0}
  #tab-rawdata .dr-dl code{background:#eef3ee;padding:1px 6px;border-radius:4px;font-size:11.5px}
  #tab-rawdata .dr-codewrap{position:relative}
  #tab-rawdata .dr-copy{position:absolute;top:8px;right:8px;background:var(--teal,#2f7d4f);color:#fff;border:0;border-radius:6px;
    padding:6px 12px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}
  #tab-rawdata pre.dr-pre{margin:0;background:#0f1c17;color:#e8f0ea;border-radius:8px;padding:14px 16px;overflow:auto;
    font-size:12px;line-height:1.5;max-height:340px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}
</style>
"""
    # hub
    cols = ""
    for title, links in HUB:
        items = ""
        for name, url, tag in links:
            t = f' <span class="dr-tag">{esc(tag)}</span>' if tag else ""
            items += f'\n          <a href="{esc(url)}" target="_blank" rel="noopener">{esc(name)}{t}</a>'
        cols += f'\n        <div class="dr-col">\n          <h4>{esc(title)}</h4>{items}\n        </div>'
    hub = f"""
      <div class="dr-hub">
        <div class="dr-ey">All source dashboards</div>
        <h3>Benefit Services — Advising &amp; Onboarding Dashboard List</h3>
        <div class="dr-url">{esc(HUB_URL)}</div>
        <a class="dr-btn" href="{esc(HUB_URL)}" target="_blank" rel="noopener">Open the dashboard hub &rarr;</a>
        <div class="dr-grid">{cols}
        </div>
        <div class="dr-note">Calendar-based unless tagged Cohort. PW = password-protected. Questions? Ask Aman Bhatia.</div>
      </div>
"""
    # component query cards, grouped by category (preserve order)
    cats = []
    for _,_,cat,_,_,_,_,_ in SEG:
        if cat not in cats: cats.append(cat)
    body = ""
    first = True
    for cat in cats:
        body += f'\n      <div class="dr-cat">{esc(cat)}</div>'
        for sid,title,c,sql,main,joins,grain,params in SEG:
            if c != cat: continue
            joins_html = ", ".join(f"<code>{esc(j)}</code>" for j in joins) if joins else "&mdash;"
            openc = ""  # all collapsed by default
            first = False
            body += f"""
      <div class="dr-card{openc}" data-seg="{esc(sid)}">
        <div class="dr-h"><div class="dr-name">{esc(title)}</div><span class="dr-car">&#9654;</span></div>
        <div class="dr-b">
          <dl class="dr-dl">
            <dt>Main table</dt><dd><code>{esc(main)}</code></dd>
            <dt>Joins</dt><dd>{joins_html}</dd>
            <dt>Grain</dt><dd>{esc(grain)}</dd>
            <dt>Params</dt><dd><code>{esc(params)}</code></dd>
          </dl>
          <div class="dr-codewrap"><button class="dr-copy" type="button">Copy</button><pre class="dr-pre">{esc(sql)}</pre></div>
        </div>
      </div>"""

    script = """
<script>
(function(){
  var root=document.getElementById("tab-rawdata"); if(!root) return;
  root.querySelectorAll(".dr-h").forEach(function(h){
    h.addEventListener("click",function(){h.closest(".dr-card").classList.toggle("open");});
  });
  root.querySelectorAll(".dr-copy").forEach(function(b){
    b.addEventListener("click",function(e){
      e.stopPropagation();
      var code=b.closest(".dr-codewrap").querySelector("pre").innerText;
      navigator.clipboard.writeText(code).then(function(){
        var t=b.textContent;b.textContent="Copied ✓";setTimeout(function(){b.textContent=t;},1200);
      });
    });
  });
})();
</script>
"""
    inner = (
      '    <div class="card drx">\n'
      '      <h2>Data Resources</h2>\n'
      '      <p class="sub">Everything behind this dashboard in one place &mdash; the source-dashboard hub, plus the exact query behind each data point. Copy &amp; run in Redash, the Snowflake MCP, or Claude. Params are inclusive date windows; runs on GUSTIE_ADHOC_WH, America/Denver.</p>\n'
      + css + hub + body + '\n    </div>\n' + script
    )
    return inner

def main():
    s = V11.read_text()
    start_tok = '<div class="tab-content" id="tab-rawdata">'
    i = s.find(start_tok)
    if i < 0: raise SystemExit("tab-rawdata not found")
    after = i + len(start_tok)
    foot = s.find('<div class="calc-footer">', after)
    if foot < 0: raise SystemExit("calc-footer after tab-rawdata not found")
    new_inner = build_inner()
    s2 = s[:after] + "\n" + new_inner + "\n    " + s[foot:]
    # guards
    assert 'class="perfDT"' in s2 and 'class="perfRE"' in s2, "date spans lost"
    assert 'id="benopsXlsxBtn"' in s2, "export button lost"
    assert s2.count(start_tok) == 1
    V11.write_text(s2)
    print(f"Data Resources tab rebuilt: {len(SEG)} query cards, hub link, {len(new_inner):,} chars injected.")
    print(f"  net size delta: {len(s2)-len(s):+,} chars")

if __name__ == "__main__":
    main()
