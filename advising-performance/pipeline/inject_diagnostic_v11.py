#!/usr/bin/env python3
"""Inject CSAT / In-App Sentiment / Email SLA diagnostic data into v11's D var.

Reads diagnostic_data.json, filters to advisors present in v11's roster, then
adds three new sibling fields to the D = { ... } object:
  csatData    = { name: { 'YYYY-MM': {sum, n, comments[]} } }
  inappData   = { name: { 'YYYY-MM': {sum, n, comments[]} } }
  emailSlaData = { name: { 'YYYY-MM': {met, total} } }
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
V11 = os.path.join(HERE, "advising_performance_dashboard_v11.html")
DIAG = os.path.join(HERE, "diagnostic_data.json")

with open(DIAG) as f:
    diag = json.load(f)
with open(V11) as f:
    html = f.read()

# Extract the roster names from peMap (already proven to work)
m = re.search(r'"peMap":\s*\{(.*?)\}', html, re.DOTALL)
peblock = m.group(1)
name_pat = re.compile(r'"([^"\\]+(?:\\.[^"\\]*)*)"\s*:')
roster = set(name_pat.findall(peblock))
print(f"Roster: {len(roster)} advisors")

# Build the three per-advisor maps for advisors in the roster
csat = {}
inapp = {}
email = {}
for name in roster:
    rec = diag.get(name, {})
    if "csat" in rec and rec["csat"]:
        csat[name] = rec["csat"]
    if "inapp" in rec and rec["inapp"]:
        inapp[name] = rec["inapp"]
    if "email" in rec and rec["email"]:
        email[name] = rec["email"]
print(f"  csat: {len(csat)} advisors  ·  inapp: {len(inapp)}  ·  email: {len(email)}")

# Serialize as compact JS object literals
def jdump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

inject = (
    ',"csatData":' + jdump(csat) +
    ',"inappData":' + jdump(inapp) +
    ',"emailSlaData":' + jdump(email)
)
print(f"Inject payload size: {len(inject):,} bytes")

# Find the end of D = { ... } and inject before the closing `}`
# D begins with `var D = {` (or `const D =`); find by anchoring on "advisors" key
# Look for the `};` that ends D — strategy: find the start, then balance braces
m = re.search(r"\bvar\s+D\s*=\s*\{", html)
if not m:
    raise RuntimeError("D = { ... } not found")
start = m.end() - 1  # position of opening {
# Brace-balance scan from `start`
depth = 0
in_str = False
str_ch = None
escaped = False
i = start
while i < len(html):
    ch = html[i]
    if escaped:
        escaped = False
    elif ch == "\\":
        escaped = True
    elif in_str:
        if ch == str_ch:
            in_str = False
    elif ch in ('"', "'"):
        in_str = True
        str_ch = ch
    elif ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            break
    i += 1
if depth != 0:
    raise RuntimeError("could not find end of D = {...}")
end_brace = i

# Inject just before end_brace — append our keys
new_html = html[:end_brace] + inject + html[end_brace:]

# Sanity: count delta
print(f"Injected {len(new_html) - len(html):,} chars  ·  new total {len(new_html):,}")

with open(V11, "w") as f:
    f.write(new_html)
print(f"Updated {V11}")
