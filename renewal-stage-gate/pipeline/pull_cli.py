#!/usr/bin/env python3
"""
Renewal Stage Gate — Phase A SF pull, CLI edition (replaces the Salesforce-MCP pull).

Pulls the in-scope Benefits-Renewal cohort + 4 related objects via the `sf` CLI,
writes the 5 `_pull_*.json` record lists in the SAME shape the MCP subagents wrote,
then runs the UNCHANGED `_assemble_sf.py` (build sf_cache.json / sf_last_updated.json
/ cohort.json) and `classify_notes.py` (sanitize recert notes → Recert_Note_Verdict,
blank raw Notes__c BEFORE anything persists). No check/metric logic changes — only
the data source moves from the MCP to the CLI.

Verbatim SOQL + cohort scope match the live pipeline:
  cohort : RecordType.Name='Benefits Renewal'
           AND StageName IN ('Recommendation Sent','Engaged','Alternatives Requested','ER Confirm')
           AND Renewal_Date__c in [floor, ceiling]   (the active +4 window)
  policies by Account__c IN; qa/atts/recert by Opportunity__c / LinkedEntityId IN.

SECURITY: raw recert Notes__c are pulled, then classify_notes.py sanitizes them in
place as the LAST SF-phase step, so no raw note text persists in sf_cache.json.
Shadow dir ($RSG_SHADOW, default /tmp/rsg_cli); live _rsg_pipeline is untouched.
"""
import datetime, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import sf_pull as S  # noqa: E402

BEN = os.environ.get("BEN", "/sessions/practical-affectionate-galileo/mnt/BenOps Dashboard Co-Work")
LIVE = os.path.join(BEN, "_rsg_pipeline")
SHADOW = os.environ.get("RSG_SHADOW", "/tmp/rsg_cli")
WORKERS = int(os.environ.get("RSG_WORKERS", "8"))
STAGES = "('Recommendation Sent','Engaged','Alternatives Requested','ER Confirm')"

def _window():
    # default to the baseline cohort.json window so a parity run diffs cleanly;
    # the live pipeline computes the active +4 window the same way each night.
    c = json.load(open(os.path.join(LIVE, "cohort.json")))
    w = c.get("window", {})
    return w.get("floor", "2026-07-01"), w.get("ceiling", "2027-01-31")

def inlist(xs): return ",".join("'%s'" % i for i in xs)

def main():
    S.assert_fresh_clock()
    floor, ceiling = _window()
    os.makedirs(SHADOW, exist_ok=True)

    # ---- 1) cohort opps (single query; nested Account/Owner preserved) ----
    opp_soql = (
        "SELECT Id, Name, AccountId, Account.Name, Account.ZP_Company_ID__c, Owner.Name, "
        "Advising_Blocked_Reason__c, Funding_Type_Status__c, Needs_Recertification__c, "
        "Offering_Selection_Deadline__c, Reason_for_Advising__c, Renewal_Date__c, Source_ID__c, "
        "Special_Enrollment__c, StageName, Stage_Detail__c, Submission_Deadline__c, SystemModstamp "
        "FROM Opportunity WHERE RecordType.Name = 'Benefits Renewal' "
        "AND StageName IN " + STAGES + " "
        f"AND Renewal_Date__c >= {floor} AND Renewal_Date__c <= {ceiling}")
    # fetch() keeps nesting off by default -> use soql_all single-shot with flatten=False
    opps = S.soql_all(lambda c: opp_soql, [1], batch=1, label="rsg_opps",
                      outdir=SHADOW, flatten=False)
    opp_ids = [o["Id"] for o in opps]
    acct_ids = sorted({o.get("AccountId") for o in opps if o.get("AccountId")})
    # cohort eff/exp date sets: new policy effective ON a renewal date; old policy
    # expiring the DAY BEFORE a renewal date (the gate tool's eff/exp convention).
    def _dbefore(s):
        y, m, dd = map(int, s.split("-"))
        return (datetime.date(y, m, dd) - datetime.timedelta(days=1)).isoformat()
    REN = sorted({o["Renewal_Date__c"] for o in opps if o.get("Renewal_Date__c")})
    DBEF = sorted({_dbefore(s) for s in REN})
    ren_lit = ",".join(REN)      # SOQL date literals are UNQUOTED
    dbef_lit = ",".join(DBEF)
    print(f"[rsg] cohort opps={len(opps)} accounts={len(acct_ids)} window={floor}..{ceiling} "
          f"renewal_dates={len(REN)}")

    # ---- 2) policies by Account__c, restricted to cohort eff/exp dates ----
    def q_pol(chunk):
        return ("SELECT Id, Name, Benefit_Type__c, Carrier__r.Name, Waiting_Period__c, "
                "Contribution_Scheme_Type__c, Contribution_for_EEs__c, Contribution_for_Dependents__c, "
                "Coverage_Effective_Date__c, Expiration_Date__c, Is_Selected__c, Policy_Status__c, "
                "Is_Base__c, Account__c, SystemModstamp FROM Policy__c WHERE Account__c IN (" + inlist(chunk) + ") "
                "AND (Coverage_Effective_Date__c IN (" + ren_lit + ") "
                "OR Expiration_Date__c IN (" + dbef_lit + "))")
    pol = S.soql_all(q_pol, acct_ids, batch=150, label="rsg_pol", outdir=SHADOW,
                     flatten=False, workers=WORKERS)

    # ---- 3) qaSheets / atts / recert by Opportunity__c / LinkedEntityId ----
    def q_qa(chunk):
        return ("SELECT Id, Opportunity__c, DBA__c, Effective_Date__c, Policy_Renewal_Date__c, "
                "Benefit_Order__c, SystemModstamp FROM QA_Sheet__c WHERE Opportunity__c IN (" + inlist(chunk) + ")")
    def q_atts(chunk):
        return ("SELECT ContentDocumentId, ContentDocument.Title, ContentDocument.FileExtension, "
                "ContentDocument.CreatedDate, LinkedEntityId, SystemModstamp "
                "FROM ContentDocumentLink WHERE LinkedEntityId IN (" + inlist(chunk) + ")")
    def q_recert(chunk):
        # recert tickets only: Escalation_Reason__c LIKE '%ecert%' (matches 'Recertification')
        return ("SELECT Id, Name, Status__c, Escalation_Reason__c, Escalation_Reason_Detail__c, "
                "Recert_Status__c, Close_Date__c, Closed_Date_Time__c, CreatedDate, Notes__c, "
                "Close_Reason__c, Opportunity__c, SystemModstamp FROM Ticket__c "
                "WHERE Opportunity__c IN (" + inlist(chunk) + ") AND Escalation_Reason__c LIKE '%ecert%'")
    qa     = S.soql_all(q_qa, opp_ids, batch=150, label="rsg_qa", outdir=SHADOW, flatten=False, workers=WORKERS)
    atts   = S.soql_all(q_atts, opp_ids, batch=150, label="rsg_atts", outdir=SHADOW, flatten=False, workers=WORKERS)
    recert = S.soql_all(q_recert, opp_ids, batch=150, label="rsg_recert", outdir=SHADOW, flatten=False, workers=WORKERS)
    print(f"[rsg] policies={len(pol)} qaSheets={len(qa)} atts={len(atts)} recert={len(recert)}")

    # ---- 4) write the 5 _pull_*.json, run unchanged assemble + sanitize ----
    def W(name, obj): json.dump(obj, open(os.path.join(SHADOW, name), "w"), default=str)
    W("_pull_opps.json", opps); W("_pull_pol.json", pol); W("_pull_qa.json", qa)
    W("_pull_recert.json", recert); W("_pull_atts.json", atts)
    shutil.copy(os.path.join(LIVE, "_assemble_sf.py"), os.path.join(SHADOW, "_assemble_sf.py"))
    shutil.copy(os.path.join(LIVE, "classify_notes.py"), os.path.join(SHADOW, "classify_notes.py"))
    for step in ("_assemble_sf.py", "classify_notes.py"):
        r = subprocess.run([sys.executable, os.path.join(SHADOW, step)], capture_output=True, text=True)
        print(f"[rsg] {step}:", r.stdout.strip(), r.stderr.strip()[:200])
    cap = S.cap_summary()
    print("[rsg] 50K-cap events:", cap if cap else "none ✅")
    # PII guard: assert no raw note text survived
    cache = json.load(open(os.path.join(SHADOW, "sf_cache.json")))
    raw = [t for t in cache["recertTickets"] if (t.get("Notes__c") or "") not in
           ("", "Recert approved — sign-off found in notes (raw note withheld; open ticket to view)")]
    print(f"[rsg] PII sanitize check: {len(raw)} tickets with residual raw notes (must be 0)")
    print("[rsg] sf_cache.json written to", SHADOW)

if __name__ == "__main__":
    main()
