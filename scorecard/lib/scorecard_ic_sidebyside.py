#!/usr/bin/env python3
"""Render IC side-by-side per PE (this quarter QTD). Static HTML, values pre-computed.
Reads scorecard_ic_data.json → writes _scorecard_ic_sbs.html + standalone BenOps_Scorecard_IC_Q2FY27.html.
Recent hires / internal transfers (new_hire_default_off.json) are flagged ** and sectioned to the RIGHT
of each PE's ramped ICs (blue divider + light background), so they don't distort the read on the team."""
import os,json,re
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,"scorecard_ic_data.json")))
META=d["meta"]; WIN=d["window"]
# --- recent-hire flag source of truth (same file the perf dashboards maintain) ---
def norm(n): return re.sub(r'[^a-z]','',(n or '').lower())
try:
    _nh=json.load(open(os.path.join(HERE,"new_hire_default_off.json")))
except Exception:
    _nh={"advising":[],"npr":[],"broker":[]}
NEW={k:{norm(x) for x in _nh.get(k,[])} for k in ("advising","npr","broker")}
LEAD2TEAM={"Micah Sanchez":"advising","Lynne Petre":"advising","Lee Ann Volosin":"npr","Aman Bhatia":"npr","Martin Ribas":"broker"}
def is_new(ic,leader): return norm(ic) in NEW.get(LEAD2TEAM.get(leader,""),set())
def val(c,k):
    n,dd=c
    if not dd: return None
    return (n/dd if k in("s","r") else 100*n/dd)
def fmt(v,k):
    if v is None: return "·"
    if k=="p": return str(round(v))
    if k=="p1": return "%.1f"%v
    return "%.2f"%v
def rag(v,g,dr,k):
    if v is None: return ""
    a = g*0.88 if dr=="hi" else g*1.25
    if k=="p1": g=100; a=94  # MRR special
    if dr=="hi": return "g" if v>=g else ("a" if v>=a else "r2")
    return "g" if v<=g else ("a" if v<=a else "r2")
def slo(g,dr,k): return ("≥" if dr=="hi" else "≤")+(str(g)+"%" if k[0]=="p" else str(g))
LEADERS=["Micah Sanchez","Lynne Petre","Lee Ann Volosin","Aman Bhatia","Martin Ribas"]
groups=sorted(d["groups"],key=lambda g:(LEADERS.index(g["leader"]) if g["leader"] in LEADERS else 9, -len(g["ics"])))

CSS="""<style>
.ic *{box-sizing:border-box}.ic{font-size:11.5px}
.ic h2{font-size:14px;font-weight:600;margin:2px 0;color:var(--text-primary)}
.ic .sub{color:var(--text-muted);font-size:11px;font-weight:400}
.ic .nt{font-size:10.5px;color:var(--text-muted);line-height:1.5;margin:6px 0 10px}
.ic .lg{display:flex;gap:10px;font-size:11px;color:var(--text-secondary);margin:2px 0 10px;flex-wrap:wrap}.ic .lg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.ic .lead{margin:16px 0 2px;font-size:12.5px;font-weight:700;color:var(--text-primary);border-top:1.5px solid var(--border-strong);padding-top:8px}
.ic .lead .r{font-weight:400;color:var(--text-muted);font-size:11px}
.ic .pe{margin:8px 0 3px;font-size:12px;font-weight:600;color:var(--text-accent)}
.ic .wrap{overflow-x:auto;border:.5px solid var(--border);border-radius:8px;margin-bottom:8px}
.ic table{border-collapse:collapse;width:100%}
.ic th,.ic td{padding:3px 6px;text-align:center;border-bottom:.5px solid var(--border);white-space:nowrap}
.ic th{font-weight:500;color:var(--text-secondary);font-size:10.5px}
.ic td.l,.ic th.l{text-align:left;min-width:180px;padding-left:8px;color:var(--text-primary);position:sticky;left:0;background:var(--bg-primary,#fff)}
.ic td.s,.ic th.s{color:var(--text-secondary);font-size:10px;min-width:40px}
.ic td.v,.ic th.v{border-left:.5px solid var(--border);min-width:60px;font-family:var(--font-mono)}
.ic th.v{font-family:inherit;font-size:10px;line-height:1.1}
.ic .g{background:var(--bg-success);color:var(--text-success)}.ic .a{background:var(--bg-warning);color:var(--text-warning)}.ic .r2{background:var(--bg-danger);color:var(--text-danger)}
.ic .na{color:var(--text-faint,#bbb)}
.ic td.nw,.ic th.nw{background:var(--surface-1,#f6f6f4)}
.ic td.nwb,.ic th.nwb{border-left:2px solid var(--text-primary,#333)}
</style>"""
H=[CSS,'<div class="ic">']
H.append(f'<h2>IC scorecard — PE by PE, ICs side by side <span class="sub">· Q2 FY27 QTD ({WIN[0][:7]}–{WIN[-1][:7]})</span></h2>')
H.append('<div class="nt">Each table = one PE (team lead); columns = that PE\'s ICs; cells = Q2 FY27 QTD (Σnum ÷ Σden). Owned-work keys off the record owner; phone/email mapped to the IC by name/agent/email (blank where unmapped). · = no volume for that IC/metric. Oct is month-to-date. ICs ordered by Q2 volume; <b>recent hires / transfers are marked ** and set off by a solid divider line</b> (no shading) — fully scored and color-coded.</div>')
H.append('<div class="lg"><span><i style="background:var(--bg-success)"></i>at/above SLO</span><span><i style="background:var(--bg-warning)"></i>near</span><span><i style="background:var(--bg-danger)"></i>below</span><span><i style="background:var(--surface-1,#f6f6f4);border:1px solid var(--border)"></i>** recent hire / transfer</span></div>')
curL=None
for g in groups:
    if g["leader"]!=curL:
        curL=g["leader"]; H.append(f'<div class="lead">{curL} <span class="r">· leader</span></div>')
    mets=g["metrics"]; leader=g["leader"]
    # ramped first (volume order preserved, stable), recent hires to the right
    ics=sorted(g["ics"],key=lambda col: 1 if is_new(col["ic"],leader) else 0)
    first_new=next((i for i,col in enumerate(ics) if is_new(col["ic"],leader)),None)
    nnew=sum(1 for col in ics if is_new(col["ic"],leader))
    def colcls(i,col):
        c="v"
        if is_new(col["ic"],leader) and i==first_new: c+=" nwb"  # solid divider only, no shading
        return c
    pehdr=f'<div class="pe">PE: {g["pe"]} <span class="sub">· {len(ics)} ICs'+(f' · {nnew} recent **' if nnew else '')+'</span></div>'
    H.append(pehdr)
    H.append('<div class="wrap"><table><thead><tr><th class="l">Metric</th><th class="s">SLO</th>')
    for i,col in enumerate(ics):
        nm=col["ic"]; parts=nm.split(); first=parts[0]; last=(parts[-1][:1]+'.') if len(parts)>1 else ''
        star=' **' if is_new(nm,leader) else ''
        H.append(f'<th class="{colcls(i,col)}" title="{nm}{star}">{first}<br>{last}{star}</th>')
    H.append('</tr></thead><tbody>')
    for m in mets:
        g0,dr,k=META[m]
        H.append(f'<tr><td class="l">{m}</td><td class="s">{slo(g0,dr,k)}</td>')
        for i,col in enumerate(ics):
            c=col["cells"].get(m)
            base=colcls(i,col)
            if not c: H.append(f'<td class="{base} na">·</td>'); continue
            v=val(c,k); H.append(f'<td class="{base} {rag(v,g0,dr,k)}">{fmt(v,k)}</td>')
        H.append('</tr>')
    H.append('</tbody></table></div>')
H.append('</div>')
frag="".join(H)
open(os.path.join(HERE,"_scorecard_ic_sbs.html"),"w",encoding="utf-8").write(frag)
standalone='<!doctype html><html><head><meta charset="utf-8"><title>IC Scorecard Q2 FY27</title><style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1400px;margin:20px auto;padding:0 14px;--text-primary:#1a1a1a;--text-secondary:#555;--text-muted:#888;--text-accent:#5b5bd6;--border:#e3e3e0;--border-strong:#c8c8c4;--surface-1:#f6f6f4;--bg-success:#d7f0dd;--text-success:#17663a;--bg-warning:#fcefcf;--text-warning:#8a5a00;--bg-danger:#fbdcdc;--text-danger:#9b1c1c;--bg-primary:#fff;--font-mono:ui-monospace,Menlo,monospace}</style></head><body>'+frag+'</body></html>'
open(os.path.join(HERE,"BenOps_Scorecard_IC_Q2FY27.html"),"w",encoding="utf-8").write(standalone)
print("wrote _scorecard_ic_sbs.html (%d bytes) + standalone"%len(frag))
