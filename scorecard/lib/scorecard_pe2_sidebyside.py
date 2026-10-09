#!/usr/bin/env python3
"""Compact inline widget: PEs side-by-side within each leader, THIS QUARTER (Q2 FY27) only.
Values pre-computed server-side; tiny JS only for expand/collapse of sub-status rows.
Reads scorecard_pe2_data.json, writes _scorecard_pe2_sbs.html."""
import os,json
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,"scorecard_pe2_data.json")))
Q=d["quarters"]; COV=d["coverage"]; LEAD=d["leaders"]
QIDX=Q[-1]["idx"]; LASTQ=Q[-1]["id"]
def qsum(c):
    n=dd=0.0
    for i in QIDX:
        if c[i] and c[i][1]: n+=c[i][0]; dd+=c[i][1]
    return (n,dd)
def value(c,k):
    n,dd=qsum(c)
    if not dd: return None
    return (n/dd if k in("s","r") else 100*n/dd)
def aggval(cols,k):
    n=dd=0.0
    for c in cols.values():
        if not c: continue
        for i in QIDX:
            if c[i] and c[i][1]: n+=c[i][0]; dd+=c[i][1]
    if not dd: return None
    return (n/dd if k in("s","r") else 100*n/dd)
def fmt(v,k):
    if v is None: return "–"
    if k=="p": return str(round(v))
    if k=="p1": return "%.1f"%v
    if k in("r","s"): return "%.2f"%v
    return str(round(v))
def rag(v,r):
    if v is None: return ""
    g=r.get("gr") if r.get("gr") is not None else r["g"]
    a=r.get("am") if r.get("am") is not None else (g*0.88 if r["d"]=="hi" else g*1.25)
    if r["d"]=="hi": return "g" if v>=g else ("a" if v>=a else "r2")
    return "g" if v<=g else ("a" if v<=a else "r2")
def slo(r): return ("≥" if r["d"]=="hi" else "≤")+(str(r["g"])+"%" if r["k"][0]=="p" else str(r["g"]))

CSS="""<style>
.sb *{box-sizing:border-box}.sb{font-size:12px}
.sb h2{font-size:14px;font-weight:600;margin:2px 0;color:var(--text-primary)}
.sb .sub{color:var(--text-muted);font-size:11px;font-weight:400}
.sb .nt{font-size:10.5px;color:var(--text-muted);line-height:1.5;margin:6px 0 10px}
.sb .bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0 10px}
.sb .bar button{font:inherit;font-size:12px;padding:4px 10px;border:.5px solid var(--border-strong);background:transparent;color:var(--text-primary);border-radius:6px;cursor:pointer}
.sb .bar button.on{background:var(--text-primary);color:var(--bg-primary,#fff)}
.sb .lg{display:flex;gap:10px;font-size:11px;color:var(--text-secondary);margin-left:auto}.sb .lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.sb .grp{margin:12px 0 4px;padding:4px 8px;background:var(--surface-2,var(--surface-1));border-radius:6px;font-size:12px;font-weight:600;color:var(--text-primary)}
.sb .grp .r{color:var(--text-muted);font-weight:400;font-size:11px}
.sb .wrap{overflow-x:auto;border:.5px solid var(--border);border-radius:8px;margin-bottom:6px}
.sb table{border-collapse:collapse;width:100%}
.sb th,.sb td{padding:4px 7px;text-align:center;border-bottom:.5px solid var(--border);white-space:nowrap}
.sb th{font-weight:500;color:var(--text-secondary);font-size:11px}
.sb td.l,.sb th.l{text-align:left;min-width:215px;padding-left:8px;color:var(--text-primary)}
.sb td.s,.sb th.s{color:var(--text-secondary);font-size:10.5px;min-width:42px}
.sb td.p,.sb th.p{border-left:1.5px solid var(--border-strong);min-width:74px;font-weight:500;font-family:var(--font-mono)}
.sb td.agg,.sb th.agg{border-left:2.5px solid var(--text-primary,#333);font-weight:700}
.sb th.p{font-family:inherit}
.sb tr.sec td{text-align:left;padding:6px 8px 3px;font-size:10px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:var(--text-accent);background:var(--surface-1)}
.sb .g{background:var(--bg-success);color:var(--text-success)}.sb .a{background:var(--bg-warning);color:var(--text-warning)}.sb .r2{background:var(--bg-danger);color:var(--text-danger)}
.sb tr.d td{font-size:10.5px}.sb tr.d td.l{padding-left:24px;color:var(--text-secondary)}
.sb tr.par{cursor:pointer}.sb .ch{display:inline-block;width:10px;font-size:9px;color:var(--text-accent)}
.sb .na{color:var(--text-faint,#bbb)}
</style>"""

def leader_rows(L):
    order=[]; seen={}
    for pe in L["pes"]:
        for r in pe["rows"]:
            if r["n"] not in seen:
                seen[r["n"]]={"n":r["n"],"sec":r["sec"],"k":r["k"],"g":r["g"],"d":r["d"],
                              "gr":r.get("gr"),"am":r.get("am"),"cols":{},"dets":{}}
                order.append(r["n"])
            o=seen[r["n"]]; o["cols"][pe["name"]]=r["c"]
            for s in r.get("det",[]):
                o["dets"].setdefault(s["n"],{})[pe["name"]]=s["c"]
    return [seen[n] for n in order]

html=[CSS,'<div class="sb">']
html.append('<h2>PEs side by side — this quarter (%s · Aug–Oct \'26) <span class="sub">· by leader</span></h2>'%LASTQ)
html.append('<div class="nt"><b>PE = the IC\'s direct manager (team lead)</b>, grouped under their leader. Kelly, Adrienne, Alex, Brooke report to <b>Aman</b> directly (ex-Rehana NP&amp;R). Cumulative Q2 FY27 QTD (Σnum ÷ Σden). Phone &amp; email by each IC\'s current PE (coverage: avail %s%%, abandon %s%%, email %s%%). Σ PEs reconciles to leader = team = scorecard (≤0.1pp). The <b>Σ column</b> after the solid line is the leader\'s volume-weighted quarter aggregate. Click ▸ to expand sub-statuses.</div>'%(COV.get("availability"),COV.get("abandon"),COV.get("email")))
html.append('<div class="bar"><button id="exp">Expand all sub-statuses</button><span class="lg"><span><i style="background:var(--bg-success)"></i>at/above SLO</span><span><i style="background:var(--bg-warning)"></i>near</span><span><i style="background:var(--bg-danger)"></i>below</span></span></div>')
rid=0
for L in LEAD:
    html.append('<div class="grp">%s <span class="r">· %s · %d PEs</span></div>'%(L["name"],"reports to Aman directly" if L["direct"] else "reports to Aman",len(L["pes"])))
    html.append('<div class="wrap"><table><thead><tr><th class="l">Metric</th><th class="s">SLO</th>')
    for pe in L["pes"]: html.append('<th class="p">%s</th>'%pe["name"])
    html.append('<th class="p agg">\u03a3 %s<span class="sub"> (all)</span></th>'%L["name"].split()[0])
    html.append('</tr></thead><tbody>')
    sec=None
    for r in leader_rows(L):
        if r["sec"]!=sec:
            sec=r["sec"]; html.append('<tr class="sec"><td colspan="%d">%s</td></tr>'%(3+len(L["pes"]),sec))
        dn=list(r["dets"].keys()); hd=len(dn)>0; rid+=1; rowid="g%d"%rid
        html.append('<tr class="%s"%s><td class="l">%s%s</td><td class="s">%s</td>'%(
            "par" if hd else "", (' data-d="%s"'%rowid) if hd else "",
            '<span class="ch">▸</span> ' if hd else "", r["n"], slo(r)))
        for pe in L["pes"]:
            c=r["cols"].get(pe["name"])
            if c is None: html.append('<td class="p na">·</td>')
            else:
                v=value(c,r["k"]); html.append('<td class="p %s">%s</td>'%(rag(v,r),fmt(v,r["k"])))
        av=aggval(r["cols"],r["k"]); html.append('<td class="p agg %s">%s</td>'%(rag(av,r),fmt(av,r["k"])))
        html.append('</tr>')
        for s in dn:
            html.append('<tr class="d" data-p="%s" style="display:none"><td class="l">%s</td><td class="s">—</td>'%(rowid,s))
            for pe in L["pes"]:
                c=r["dets"][s].get(pe["name"])
                if c is None: html.append('<td class="p na">·</td>')
                else:
                    v=value(c,r["k"]); html.append('<td class="p %s">%s</td>'%(rag(v,r),fmt(v,r["k"])))
            av=aggval(r["dets"][s],r["k"]); html.append('<td class="p agg %s">%s</td>'%(rag(av,r),fmt(av,r["k"])))
            html.append('</tr>')
    html.append('</tbody></table></div>')
html.append('</div>')
html.append("""<script>
(function(){var root=document.currentScript.parentNode;
root.querySelectorAll('tr.par').forEach(function(tr){tr.onclick=function(){var rs=root.querySelectorAll('tr[data-p="'+tr.dataset.d+'"]');var sh=rs[0].style.display==='none';rs.forEach(function(x){x.style.display=sh?'table-row':'none';});tr.querySelector('.ch').textContent=sh?'▾':'▸';};});
var b=document.getElementById('exp');b.onclick=function(){var open=b.textContent[0]==='E';root.querySelectorAll('tr.d').forEach(function(x){x.style.display=open?'table-row':'none';});root.querySelectorAll('tr.par .ch').forEach(function(c){c.textContent=open?'▾':'▸';});b.textContent=open?'Collapse sub-statuses':'Expand all sub-statuses';b.classList.toggle('on',open);};})();
</script>""")
frag="".join(html)
open(os.path.join(HERE,"_scorecard_pe2_sbs.html"),"w",encoding="utf-8").write(frag)
print("wrote _scorecard_pe2_sbs.html (%d bytes)"%len(frag))
