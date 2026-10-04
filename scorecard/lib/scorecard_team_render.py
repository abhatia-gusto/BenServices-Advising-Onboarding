#!/usr/bin/env python3
"""Render scorecard_team_data.json -> (1) _scorecard_team_widget.html (paste into show_widget), (2) standalone
BenOps_Scorecard_TeamView_<Mon><YYYY>.html. Quarters are cumulative sums (sum num / sum den), fiscal May-Apr."""
import os,json,calendar
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,"scorecard_team_data.json")))
def val(n,dd,k): return None if not dd else (round(100*n/dd,1) if k[0]=="p" else round(n/dd,2))
def conv(r,k):
    qs=[val(sum(r["c"][i][0] for i in q["idx"]),sum(r["c"][i][1] for i in q["idx"]),k) for q in d["quarters"]]
    return qs,[val(c[0],c[1],k) for c in r["c"]]
T=[]
for t in d["teams"]:
    S={};order=[]
    for r in t["rows"]:
        s=r.get("sec","Metrics")
        if s not in S: S[s]=[];order.append(s)
        q,m=conv(r,r["k"]); o=[r["n"],r["k"],r["g"],r["d"],r.get("gr"),r.get("am"),q,m]
        if r.get("det"): o.append([[x["n"]]+list(conv(x,r["k"])) for x in r["det"]])
        S[s].append(o)
    T.append([t["name"],[[s,S[s]] for s in order]])
MN=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
ML=[MN[int(m[5:7])-1] for m in d["months"]]
Q=[]
for q in d["quarters"]:
    a,b=d["months"][q["idx"][0]],d["months"][q["idx"][-1]]
    lab=MN[int(a[5:7])-1]+"–"+MN[int(b[5:7])-1] if a!=b else MN[int(a[5:7])-1]
    Q.append({"id":q["id"]+(" QTD" if q["partial"] else ""),"idx":q["idx"],"l":lab+" '"+b[2:4]})
thru=d["through"]; mon=MN[int(thru[5:7])-1]; yr=thru[:4]
note=("Fiscal quarters run May–Apr; cells are cumulative (Σnumerator ÷ Σdenominator). "+("Last quarter is quarter-to-date. " if d["quarters"][-1]["partial"] else "")+
 "† = ownership assumption (Ready by 1st &amp; OA→Advising Ticket SLA → Advising; Ful→OA Ticket SLA → NP&amp;R; Email SLO by responding owner's team). "
 "Phone abandon SLO ≤30%. Latest-month Benefit Order ≤30d is understated (30-day window not elapsed). "
 "Net MRR Retention uses "+d["mrrfile"]+" (closes through "+d.get("mrrmax","?")+") — refresh the MRR feed if stale. BYB/BT phone ramped up in 2026.")
tpl=open(os.path.join(HERE,"scorecard_team_widget.template.html")).read()
frag=tpl.replace("__Q__",json.dumps(Q,ensure_ascii=False)).replace("__ML__",json.dumps(ML)).replace("__T__",json.dumps(T,ensure_ascii=False,separators=(",",":"))).replace("__NOTE__",note)
open(os.path.join(HERE,"_scorecard_team_widget.html"),"w").write(frag)
css=":root{--border:#e5e7eb;--border-strong:#cfd4da;--text-primary:#1f2328;--text-secondary:#555d66;--text-muted:#6b7280;--text-accent:#2a5bd7;--surface-1:#f6f7f9;--bg-primary:#fff;--bg-success:#dff3e3;--text-success:#14602b;--bg-warning:#fdf0cc;--text-warning:#7a5200;--bg-danger:#fbdcdc;--text-danger:#a11b1b;--font-mono:ui-monospace,Menlo,monospace}body{margin:0;padding:18px 20px;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;color:#1f2328;background:#fff}@media(prefers-color-scheme:dark){:root{--border:#2b2f36;--border-strong:#3a3f48;--text-primary:#e8eaed;--text-secondary:#b4b9bf;--text-muted:#9aa0a6;--text-accent:#7aa2ff;--surface-1:#1d2025;--bg-primary:#16181c;--bg-success:#173a22;--text-success:#8fe0a6;--bg-warning:#4a3a0c;--text-warning:#f5cf6b;--bg-danger:#4a1c1c;--text-danger:#ff9c9c}body{background:#16181c;color:#e8eaed}}"
out="BenOps_Scorecard_TeamView_%s%s.html"%(mon,yr)
open(os.path.join(HERE,out),"w").write('<!DOCTYPE html><html><head><meta charset="utf-8"><title>Benefit Services Scorecard — Team View, %s %s</title><style>%s</style></head><body><h2 style="font-size:17px;margin:0 0 4px">Benefit Services Scorecard — Team View (through %s %s)</h2>%s</body></html>'%(mon,yr,css,mon,yr,frag))
print("wrote",out,"and _scorecard_team_widget.html;",len(frag),"bytes")
