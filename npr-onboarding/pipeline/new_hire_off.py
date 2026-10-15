#!/usr/bin/env python3
"""Shared helper: seed each performance dashboard's default-UNCHECKED roster from
new_hire_default_off.json so newly-hired ICs start unchecked in the default view
(until they ramp). Single source of truth = new_hire_default_off.json at project root.

To RE-ENABLE someone once they've ramped: remove their name from the relevant list in
new_hire_default_off.json, then rebuild/republish that dashboard. To add new hires, add
their names to the list. No code changes needed.

Each generator calls apply(html, dash, json_path) on its HTML string right before writing,
so the behavior survives every refresh. The transforms are idempotent: Advising re-seeds the
DEFAULT_OFF set each build; NPR/Broker only rewrite the untouched original function text
(if already patched, the match fails and the html is returned unchanged).
"""
import json
import re


def _arr(names):
    return "[" + ",".join(json.dumps(n) for n in names) + "]"


def apply(html, dash, json_path):
    try:
        data = json.load(open(json_path))
    except FileNotFoundError:
        return html
    names = data.get(dash, []) or []
    arr = _arr(names)

    if dash == "advising":
        # Seed the existing DEFAULT_OFF name-set (idempotent; replaces whatever is there).
        html = re.sub(
            r'var DEFAULT_OFF=new Set\(\[[^\]]*\]\);',
            'var DEFAULT_OFF=new Set(' + arr + ');',
            html, count=1,
        )

    elif dash == "npr":
        old = ('function autoAdv(){var all=DATA.ics.map(function(i){return i.name});'
               'var hd=DATA.ics.filter(function(a){return computeRow(a).weighted!=null}).map(function(a){return a.name});'
               'state.adv=(hd.length&&hd.length<all.length)?hd:[];}')
        new = ('var NEW_HIRE_OFF=new Set(' + arr + ');'
               'function autoAdv(){var all=DATA.ics.map(function(i){return i.name});'
               'var hd=DATA.ics.filter(function(a){return computeRow(a).weighted!=null}).map(function(a){return a.name});'
               'var base=(hd.length&&hd.length<all.length)?hd:all;'
               'state.adv=base.filter(function(n){return !NEW_HIRE_OFF.has(n)});}')
        if old in html:
            html = html.replace(old, new, 1)
        else:
            # already patched in a prior run → just refresh the name set (idempotent/updatable)
            html = re.sub(r'var NEW_HIRE_OFF=new Set\(\[[^\]]*\]\);',
                          'var NEW_HIRE_OFF=new Set(' + arr + ');', html, count=1)

    elif dash == "broker":
        old = ('function autoSelectICs(){var advs=grp().advisors,names=advs.map(function(a){return a.name}),'
               'hd=advs.filter(function(a){return computeRow(a).weighted!=null}).map(function(a){return a.name});'
               'sIC=new Set((hd.length&&hd.length<names.length)?hd:names);}')
        new = ('var NEW_HIRE_OFF=new Set(' + arr + ');'
               'function autoSelectICs(){var advs=grp().advisors,names=advs.map(function(a){return a.name}),'
               'hd=advs.filter(function(a){return computeRow(a).weighted!=null}).map(function(a){return a.name});'
               'var base=(hd.length&&hd.length<names.length)?hd:names;'
               'sIC=new Set(base.filter(function(n){return !NEW_HIRE_OFF.has(n)}));}')
        if old in html:
            html = html.replace(old, new, 1)
        else:
            html = re.sub(r'var NEW_HIRE_OFF=new Set\(\[[^\]]*\]\);',
                          'var NEW_HIRE_OFF=new Set(' + arr + ');', html, count=1)

    return html
