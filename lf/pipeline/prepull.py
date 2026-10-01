#!/usr/bin/env python3
"""
LF Conversion — CLI pre-pull of the classifier bundle (replaces in-subagent/MCP SOQL).

For each in-scope opp, pulls the SAME 3 narrative channels the classifier reasons over
(Notes__c, OpportunityFeed TextPost/ContentPost, Benefits-Renewal-Case EmailMessage bodies)
via the `sf` CLI and writes a BYTE-STABLE bundle JSON to disk. The classifier itself is
UNCHANGED — Claude subagents read these bundles from disk (per classifier_instructions.md)
instead of calling the MCP. Rubric / taxonomy / caps / cleaning are identical to the live
pipeline (clean() 2500/400/600, QUOTE_MARKERS history strip, NOISE_RE drop) so each opp's
incremental bundle-hash stays stable.

SOQL note: EmailMessage uses the NESTED Parent.Opportunity__c (no `oid` alias — aliases are
only legal in aggregate queries; the alias form returns 0 rows), + the Benefits-Renewal-Case
record-type filter.
"""
import json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import sf_pull as S  # noqa: E402

BEN = os.environ.get("BEN", "/sessions/practical-affectionate-galileo/mnt/BenOps Dashboard Co-Work")
IDS = os.environ.get("LF_IDS", "/tmp/lf_open_ids.json")
OUT = os.environ.get("LF_OUT", "/tmp/lf_cli")
WORKERS = int(os.environ.get("LF_WORKERS", "8"))

# --- verbatim from lf_signal_classifier.py (bundle construction unchanged) ---
QUOTE_MARKERS = re.compile(
    r"(^\s*From:\s|-----Original Message-----|________+|^\s*On .*wrote:|"
    r"\bref:!|This message,? and any attachments)", re.M)
NOISE_RE = re.compile(r"(out of (the )?office|automatic reply|do not reply|unsubscribe)", re.I)

def clean(txt, cap=900):
    if not txt: return ""
    m = QUOTE_MARKERS.search(txt)
    if m: txt = txt[:m.start()]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt)).strip()[:cap]

def inlist(xs): return ",".join(f"'{i}'" for i in xs)

def main():
    S.assert_fresh_clock()
    ids = json.load(open(IDS))
    ids = [i[:18] for i in ids]            # SOQL IN matches 15/18; feed/email keys are 18
    os.makedirs(OUT, exist_ok=True)
    print(f"[lf] opps={len(ids)} out={OUT} workers={WORKERS}")

    bundles = {i[:15]: {"notes": "", "status": "", "fts": "", "posts": [], "emails": []} for i in ids}

    # 1) Opportunity notes/status/fts
    def q_opp(c): return ("SELECT Id, Notes__c, StageName, Funding_Type_Status__c "
                          "FROM Opportunity WHERE Id IN (" + inlist(c) + ")")
    t0 = time.time()
    for r in S.soql_all(q_opp, ids, batch=120, label="lf_opp", outdir=OUT, workers=WORKERS):
        d = bundles.get((r.get("Id") or "")[:15])
        if d:
            d["notes"] = clean(r.get("Notes__c"), 2500)
            d["status"] = r.get("StageName") or ""
            d["fts"] = r.get("Funding_Type_Status__c") or ""

    # 2) OpportunityFeed posts (ordered)
    def q_feed(c): return ("SELECT ParentId, Type, Body, CreatedDate FROM OpportunityFeed "
                           "WHERE ParentId IN (" + inlist(c) + ") AND Type IN ('TextPost','ContentPost') "
                           "ORDER BY ParentId, CreatedDate")
    feed = S.soql_all(q_feed, ids, batch=120, label="lf_feed", outdir=OUT, workers=WORKERS)
    feed.sort(key=lambda r: (r.get("ParentId") or "", r.get("CreatedDate") or ""))
    for r in feed:
        d = bundles.get((r.get("ParentId") or "")[:15]); b = clean(r.get("Body"), 400)
        if d and b: d["posts"].append(b)

    # 3) EmailMessage renewal-case bodies (nested Parent.Opportunity__c; NO alias)
    def q_email(c): return ("SELECT Parent.Opportunity__c, Incoming, Subject, TextBody, MessageDate "
                            "FROM EmailMessage WHERE Parent.Opportunity__c IN (" + inlist(c) + ") "
                            "AND Parent.RecordType.Name='Benefits Renewal Case' "
                            "ORDER BY Parent.Opportunity__c, MessageDate")
    emails = S.soql_all(q_email, ids, batch=120, label="lf_email", outdir=OUT, workers=WORKERS, flatten=False)
    emails.sort(key=lambda r: (((r.get("Parent") or {}).get("Opportunity__c") or ""), r.get("MessageDate") or ""))
    nmail = 0
    for r in emails:
        oid = ((r.get("Parent") or {}).get("Opportunity__c") or "")[:15]
        d = bundles.get(oid)
        if not d: continue
        body = clean(r.get("TextBody"), 600); subj = (r.get("Subject") or "").strip()[:160]
        if NOISE_RE.search(subj + " " + body): continue
        d["emails"].append(["in" if r.get("Incoming") else "out", subj, body]); nmail += 1

    # byte-stable serialization (sorted keys)
    with open(os.path.join(OUT, "bundles.json"), "w") as fh:
        json.dump(bundles, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    npost = sum(len(v["posts"]) for v in bundles.values())
    nnotes = sum(1 for v in bundles.values() if v["notes"])
    print(f"[lf] notes={nnotes} posts={npost} emails={nmail} in {time.time()-t0:.0f}s")
    print("[lf] 50K-cap events:", S.cap_summary() or "none ✅")
    print("[lf] bundles.json ->", os.path.join(OUT, "bundles.json"))

if __name__ == "__main__":
    main()
