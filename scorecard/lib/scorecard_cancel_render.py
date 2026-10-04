#!/usr/bin/env python3
"""Cancel-rate charts for the scorecard (inline widget). NP = coverage-effective COHORT (operating-metrics embed);
BYB / BT = CLOSE MONTH (FIRST_END_MONTH). Usage: python3 scorecard_cancel_render.py --through YYYY-MM [--start YYYY-MM]
Writes _scorecard_cancel_widget.html (paste into show_widget, Chart.js from cdnjs)."""
import os,sys,csv,io,glob,json
HERE=os.path.dirname(os.path.abspath(__file__)); csv.field_size_limit(10**7)
a=sys.argv
THROUGH=a[a.index("--through")+1] if "--through" in a else "2026-09"
START=a[a.index("--start")+1] if "--start" in a else "2024-04"
MN=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
def mr(s,e):
    y,m=int(s[:4]),int(s[5:7]); out=[]
    while "%04d-%02d"%(y,m)<=e:
        out.append("%04d-%02d"%(y,m)); m+=1
        if m==13: y+=1; m=1
    return out
months=mr(START,THROUGH); labels=[MN[int(m[5:7])-1]+" '"+m[2:4] for m in months]
def ma3(v): return [None if i<2 or any(x is None for x in v[i-2:i+1]) else round(sum(v[i-2:i+1])/3,1) for i in range(len(v))]
# NP cohort
h=open(os.path.join(HERE,"benservices_operating_metrics_dashboard_v1.html"),encoding="utf-8",errors="replace").read()
i=h.find('id="embeddedData"'); s=h.find(">",i)+1; e=h.find("</script>",s)
recs=[r for r in csv.DictReader(io.StringIO(h[s:e].strip())) if r["RECORD_TYPE"]=="New Plan"]
np_p=[];np_t=[];np_c=[]
for m in months:
    r=next((r for r in recs if r["COHORT_MONTH"][:7]==m),None)
    np_p.append(round(float(r["PCT_CANCELED"]),1) if r and r["PCT_CANCELED"] else None); np_t.append(int(float(r["TOTAL_ORDERS"])) if r else 0); np_c.append(int(float(r["CANCEL_COUNT"])) if r and r["CANCEL_COUNT"] else 0)
def close_month(pat):
    p=sorted(glob.glob(os.path.join(HERE,"queries",pat)))[-1]; acc={}
    for r in csv.DictReader(open(p,newline="",encoding="utf-8",errors="replace")):
        mo=(r.get("FIRST_END_MONTH") or "")[:7]; c=(r.get("CANCEL_FLAG") or "").strip().lower()
        try:
            if float(r.get("DAYS_CREATED_TO_FIRST_FULFILLED") or 0)>1000: continue  # legacy admin closes
        except ValueError: pass
        if len(mo)<7 or c not in("0","1","0.0","1.0","true","false"): continue
        x=acc.setdefault(mo,[0,0]); x[1]+=1; x[0]+=c in("1","1.0","true")
    return ([round(100*acc[m][0]/acc[m][1],1) if m in acc else None for m in months],[acc.get(m,[0,0])[1] for m in months],[acc.get(m,[0,0])[0] for m in months])
byb=close_month("byb_data_2024-01-01_to_*.csv"); bt=close_month("bt_data_2024-01-01_to_*.csv")
CH=[{"id":"np","title":"New Plan — cancel rate · by coverage-effective cohort","pct":np_p,"tot":np_t,"can":np_c,"goal":15,"gl":"goal ≤15%"},
    {"id":"byb","title":"BYB — cancel rate · by close month","pct":byb[0],"tot":byb[1],"can":byb[2],"goal":15,"gl":"goal ≤15%"},
    {"id":"bt","title":"BT — cancel rate · by close month","pct":bt[0],"tot":bt[1],"can":bt[2],"goal":10,"gl":"goal ≤10%"}]
for c in CH: c["ma"]=ma3(c["pct"])
html='''<div class="cc"><style>.cc h3{font-size:13px;font-weight:500;margin:14px 0 4px;color:var(--text-primary)}.cc .lg{margin-left:0;display:flex;gap:14px;font-size:11px;color:var(--text-secondary);margin:2px 0 6px;flex-wrap:wrap}.cc .lg i{display:inline-block;width:14px;height:3px;margin-right:5px;vertical-align:middle}.cc .nt{font-size:10.5px;color:var(--text-muted);margin-top:6px}</style>
<div class="lg"><span><i style="background:#EA6A33"></i>% cancel rate</span><span><i style="background:#0B8A7A"></i>3-mo moving avg</span><span><i style="background:#9a9a96;height:2px"></i>goal</span><span><i style="background:#C5CFE6;height:9px"></i>BOs</span><span><i style="background:#F0B49A;height:9px"></i>cancelled BOs</span></div>
<h3>New Plan — cancel rate · by coverage-effective cohort</h3><div style="position:relative;height:230px"><canvas id="c_np"></canvas></div>
<h3>BYB — cancel rate · by close month</h3><div style="position:relative;height:230px"><canvas id="c_byb"></canvas></div>
<h3>BT — cancel rate · by close month</h3><div style="position:relative;height:230px"><canvas id="c_bt"></canvas></div>
<div class="nt">New Plan is cohort-based (coverage-effective month); BYB and BT are by close month (FIRST_END_MONTH). Bars = BOs in the month, orange = cancelled.</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const L=__L__;const CH=__CH__;
CH.forEach(c=>{const mx=Math.max.apply(null,c.tot);
 new Chart(document.getElementById('c_'+c.id),{data:{labels:L,datasets:[
 {type:'bar',data:c.tot,backgroundColor:'#C5CFE6',yAxisID:'y1',order:5,barPercentage:.7},
 {type:'bar',data:c.can,backgroundColor:'#F0B49A',yAxisID:'y1',order:4,barPercentage:.4},
 {type:'line',data:L.map(()=>c.goal),borderColor:'#9a9a96',borderDash:[5,4],borderWidth:1.3,pointRadius:0,yAxisID:'y',order:3},
 {type:'line',data:c.ma,borderColor:'#0B8A7A',borderDash:[6,4],borderWidth:2.2,pointRadius:0,tension:.25,spanGaps:true,yAxisID:'y',order:2},
 {type:'line',data:c.pct,borderColor:'#EA6A33',borderWidth:2.8,pointRadius:0,pointHoverRadius:4,tension:.25,spanGaps:true,yAxisID:'y',order:1}]},
 options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{callbacks:{label:t=>{const i=t.datasetIndex;const n=['BOs','Cancelled','Goal','3-mo avg','Cancel rate'][i];return n+': '+(t.parsed.y==null?'–':(i>=2?t.parsed.y+'%':t.parsed.y));}}}},
 scales:{y:{min:0,max:Math.max(28,Math.ceil(Math.max.apply(null,c.pct.filter(x=>x!=null))*1.1)),ticks:{callback:v=>v+'%',color:'#898781'},grid:{color:'rgba(128,128,128,.12)'}},y1:{position:'right',min:0,max:Math.ceil(mx*(c.id=='np'?1.15:3.0)/100)*100,grid:{display:false},ticks:{color:'#898781'},title:{display:true,text:'BO count',color:'#898781',font:{size:10}}},x:{grid:{display:false},ticks:{color:'#898781',maxRotation:45,autoSkip:true,font:{size:10}}}}}});});
</script>'''
html=html.replace("__L__",json.dumps(labels)).replace("__CH__",json.dumps(CH))
open(os.path.join(HERE,"_scorecard_cancel_widget.html"),"w").write(html)
print("wrote _scorecard_cancel_widget.html",len(html),"bytes;",len(months),"months")

# combined widget (team tables + cancel charts in one show_widget call)
_t=os.path.join(HERE,"_scorecard_team_widget.html")
if os.path.exists(_t):
    comb=open(_t).read()+'\n<div style="font-size:13px;font-weight:500;margin:14px 0 0;color:var(--text-primary);border-top:0.5px solid var(--border);padding-top:12px">Cancel rate trends</div>\n'+html
    open(os.path.join(HERE,"_scorecard_combined_widget.html"),"w").write(comb); print("wrote _scorecard_combined_widget.html",len(comb))
