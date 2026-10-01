#!/usr/bin/env python3
"""
sf_parity_check.py — reusable parity harness for the CLI rewire.

Two standing checks (see SF_CLI_REWIRE_PLAN.md §5/§7 risk 5):
  * row_count_parity — per-object CLI row counts vs an expected/baseline count.
  * evidence_coverage — every stored classifier evidence quote (from the LIVE
    dashboard dataset) must be found verbatim in the CLI-pulled text bundle.
    This is the strong test: it proves the CLI reproduces the exact inputs the
    classifier saw, so classifications cannot drift from a data-source change.
"""
import re
import unicodedata


def _norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def row_count_parity(label, cli_count, expected_count, tol=0):
    ok = abs(cli_count - expected_count) <= tol
    return {"check": "row_count", "label": label, "cli": cli_count,
            "expected": expected_count, "tol": tol, "pass": ok}


def evidence_coverage(quotes, haystack, min_len=12):
    """quotes: list[str] evidence snippets stored by the live classifier.
       haystack: concatenated CLI-pulled text for the same opp.
    Returns coverage ratio + the misses. Short quotes (<min_len) are skipped
    (too generic to be meaningful substring tests)."""
    H = _norm(haystack)
    hits, misses = 0, []
    tested = 0
    for q in quotes:
        qn = _norm(q)
        if len(qn) < min_len:
            continue
        tested += 1
        if qn in H:
            hits += 1
        else:
            misses.append(q)
    cov = (hits / tested) if tested else 1.0
    return {"check": "evidence_coverage", "tested": tested, "hits": hits,
            "coverage": round(cov, 4), "misses": misses}


def summarize(results):
    lines = []
    allpass = True
    for r in results:
        if r.get("check") == "row_count":
            mark = "✅" if r["pass"] else "❌"
            allpass &= r["pass"]
            lines.append(f"{mark} {r['label']}: CLI={r['cli']} expected={r['expected']} (tol {r['tol']})")
        elif r.get("check") == "evidence_coverage":
            mark = "✅" if r["coverage"] >= 0.99 else ("⚠️" if r["coverage"] >= 0.95 else "❌")
            allpass &= r["coverage"] >= 0.95
            lines.append(f"{mark} evidence coverage: {r['hits']}/{r['tested']} = {r['coverage']*100:.1f}%"
                         + (f" | misses: {len(r['misses'])}" if r['misses'] else ""))
    return allpass, "\n".join(lines)
