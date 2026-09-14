#!/usr/bin/env python3
# Generate SOQL batch files for a group over an opp-index range.
# Usage: gen_soql.py <group: intro|recert|pk> <start_idx> <end_idx> <batch_size>
# Writes soql files to _pull/soql/<group>_<start>_<batchidx>.sql and prints their paths.
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.abspath(os.path.join(HERE, ".."))
SOQL = os.path.join(HERE, "soql")
os.makedirs(SOQL, exist_ok=True)

group = sys.argv[1]
start = int(sys.argv[2]); end = int(sys.argv[3]); bs = int(sys.argv[4])

# Open/PF universe (closed==false). Self-heal: build _openpf_ids.json from the
# freshly-assembled dataset if it's absent, so the recipe is self-contained.
IDS_PATH = os.path.join(OUT, "_openpf_ids.json")
if not os.path.exists(IDS_PATH):
    data = json.load(open(os.path.join(os.path.dirname(OUT), "advising_vnext_data.json")))
    openpf = [o["opp_id18"] for o in data if not o.get("closed")]
    json.dump(openpf, open(IDS_PATH, "w"))
    sys.stderr.write(f"[gen_soql] built _openpf_ids.json ({len(openpf)} open/PF opps)\n")
ids = json.load(open(IDS_PATH))
sub = ids[start:end]

def inlist(xs): return ",".join("'%s'"%i for i in xs)

def soql_for(chunk):
    if group == "intro":
        return ("SELECT Opportunity__c oid, MIN(CreatedDate) mind FROM Case "
                "WHERE RecordType.Name='Benefits Renewal Case' AND Intro_Call_Completed__c=true "
                "AND Opportunity__c IN ("+inlist(chunk)+") GROUP BY Opportunity__c")
    if group == "recert":
        return ("SELECT Opportunity__c, Recert_Status__c, CreatedDate FROM Ticket__c "
                "WHERE Recert_Status__c != null AND Opportunity__c IN ("+inlist(chunk)+")")
    if group == "pk":
        return ("SELECT LinkedEntityId, ContentDocument.Title, ContentDocument.CreatedDate "
                "FROM ContentDocumentLink WHERE ContentDocument.Title LIKE '%Renewal Packet%' "
                "AND LinkedEntityId IN ("+inlist(chunk)+")")
    if group == "sep":
        return ("SELECT Id oid, SEP_Risk_Level__c sep FROM Opportunity "
                "WHERE Id IN ("+inlist(chunk)+")")
    raise SystemExit("bad group")

paths=[]
for j in range(0, len(sub), bs):
    chunk = sub[j:j+bs]
    p = os.path.join(SOQL, f"{group}_{start}_{j//bs}.sql")
    open(p,"w").write(soql_for(chunk))
    paths.append(p)
for p in paths: print(p)
