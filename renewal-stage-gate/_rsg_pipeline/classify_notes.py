# SF-phase note classifier: sanitize recert ticket notes in sf_cache.json IN PLACE.
# Runs in the Salesforce phase so raw note text NEVER persists past the SF pull.
# Uses the original tool's approval-line regex + negation guard. Idempotent.
import re, json, sys, os
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sf_cache.json")
NEG = re.compile(r"\b(not|never|non|un|isn'?t|wasn'?t|no)[\s-]*approv|await\w*\s+approv|pend\w*\s+approv|need\w*\s+approv|request\w*\s+approv|denied|declin", re.I)
def approved(*texts):
    for t in texts:
        if not t: continue
        for s in re.split(r"\r?\n", str(t)):
            s = s.strip()
            if s and re.search(r"approv", s, re.I) and not NEG.search(s):
                return True
    return False
d = json.load(open(CACHE))
n = 0
for t in d.get("recertTickets", []):
    appr = approved(t.get("Notes__c"), t.get("Close_Reason__c"))
    t["Recert_Note_Verdict"] = "approved_in_notes" if appr else "no_approval_evidenced"
    t["Notes__c"] = ("Recert approved — sign-off found in notes (raw note withheld; open ticket to view)"
                     if appr else "")
    t["Close_Reason__c"] = ""
    n += 1
json.dump(d, open(CACHE, "w"), default=str)
print("classified + sanitized %d recert ticket(s); no raw note text remains in sf_cache.json" % n)
