#!/usr/bin/env python3
"""Inject per-month calls + Level-AI-channels data into v11.

Adds two top-level fields to D:
  - callsByMo:   { name: { 'YYYY-MM': {inbound, outbound, total, durations...} } }
  - levelAiChannelsByMo: { name: { 'YYYY-MM': {call: n, email: n, ...} } }
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
V11 = os.path.join(HERE, "advising_performance_dashboard_v11.html")
PERIOD = os.path.join(HERE, "v11_period_data.json")

with open(PERIOD) as f:
    period = json.load(f)
with open(V11) as f:
    html = f.read()

# Filter to roster
m = re.search(r'"peMap":\s*\{(.*?)\}', html, re.DOTALL)
peblock = m.group(1)
name_pat = re.compile(r'"([^"\\]+(?:\\.[^"\\]*)*)"\s*:')
roster = set(name_pat.findall(peblock))

calls = {n: period["callsByMo"][n] for n in roster if n in period.get("callsByMo", {})}
chan = {n: period["levelaiChannelsByMo"][n] for n in roster if n in period.get("levelaiChannelsByMo", {})}
print(f"Roster: {len(roster)} · calls: {len(calls)} · levelAi channels: {len(chan)}")

# Strip prior injections if present
for key in ("callsByMo", "levelAiChannelsByMo"):
    m2 = re.search(r',"' + key + r'":', html)
    if not m2: continue
    start = m2.start()
    i = m2.end()
    while i < len(html) and html[i] in " \t\n": i += 1
    if html[i] != "{": continue
    depth = 0; in_str = False; str_ch = None; escaped = False
    while i < len(html):
        ch = html[i]
        if escaped: escaped = False
        elif ch == "\\": escaped = True
        elif in_str:
            if ch == str_ch: in_str = False
        elif ch in ('"', "'"):
            in_str = True; str_ch = ch
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    print(f"  stripping prior {key}")
    html = html[:start] + html[end:]

def jdump(obj): return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
inject = ',"callsByMo":' + jdump(calls) + ',"levelAiChannelsByMo":' + jdump(chan)

# Find end of D = { ... } and inject
m3 = re.search(r"\bvar\s+D\s*=\s*\{", html)
start = m3.end() - 1
depth = 0; in_str = False; str_ch = None; escaped = False
i = start
while i < len(html):
    ch = html[i]
    if escaped: escaped = False
    elif ch == "\\": escaped = True
    elif in_str:
        if ch == str_ch: in_str = False
    elif ch in ('"', "'"):
        in_str = True; str_ch = ch
    elif ch == "{": depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0: break
    i += 1
end_brace = i

new_html = html[:end_brace] + inject + html[end_brace:]
with open(V11, "w") as f: f.write(new_html)
print(f"Injected {len(new_html) - len(html):,} chars  ·  new total {len(new_html):,}")
