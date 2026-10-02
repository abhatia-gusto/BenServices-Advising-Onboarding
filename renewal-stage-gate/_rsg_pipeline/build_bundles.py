# Snowflake phase (LIGHT): add SNOW_A-F facts to the SF fields already in sf_cache.json.
# Parallel (thread pool w/ per-thread connection) + resumable (skips opps already in rsg_bundles.json).
# Notes are already classified/sanitized by the SF phase (classify_notes.py); 9A address reduced here.
import re, json, os, datetime, threading, time, concurrent.futures as cf
import snowflake.connector

P     = os.path.dirname(os.path.abspath(__file__))
HTML  = P + "/renewal-gate-check-tool.html"
SF    = P + "/sf_cache.json"
SCHEME= P + "/scheme.txt"
OUT   = P + "/rsg_bundles.json"
PATENV= os.path.dirname(P) + "/snowflake_pat.env"
W = "DATA_WAREHOUSE_RC1.HAWAIIAN_ICE_PRODUCTION_NO_PII"
WORKERS = int(os.environ.get("RSG_WORKERS", "8"))
LIMIT   = int(os.environ.get("RSG_LIMIT", "0"))   # 0 = all

html = open(HTML).read()
def snow_sql(name, rid, date, dbefore):
    i = html.index("function SNOW_%s(" % name); b1 = html.index("`", i); b2 = html.index("`", b1+1)
    return (html[b1+1:b2].replace("${W}", W).replace("${RID}", str(rid))
            .replace("${DATE}", date).replace("${DBEFORE}", dbefore))
def day_before(iso):
    return (datetime.date.fromisoformat(iso) - datetime.timedelta(days=1)).isoformat()

def _envcfg(path):
    cfg = {}
    for ln in open(path):
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln: continue
        k, v = ln.split("=", 1); cfg[k.strip()] = v.strip()
    return cfg
_CFG = _envcfg(PATENV)                       # account/user/role/warehouse come from snowflake_pat.env
PAT  = _CFG["SNOWFLAKE_PAT"]                  # -> machine-agnostic; no hardcoded identity
_tl = threading.local()
def conn():
    c = getattr(_tl, "c", None)
    if c is None:
        c = snowflake.connector.connect(
            account=_CFG.get("SNOWFLAKE_ACCOUNT", "GUSTO-WAREHOUSE"),
            user=_CFG["SNOWFLAKE_USER"],
            role=_CFG.get("SNOWFLAKE_ROLE", "FR_PROD_SNOWFLAKE_GUSTIE_INTERNAL"),
            warehouse=_CFG.get("SNOWFLAKE_WAREHOUSE", "GUSTIE_ADHOC_WH"),
            authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=PAT)
        _tl.c = c
    return c
def run_snow(name, rid, date, dbefore):
    cur = conn().cursor(snowflake.connector.DictCursor)
    try: cur.execute(snow_sql(name, rid, date, dbefore)); return cur.fetchall()
    finally: cur.close()

sf = json.load(open(SF))
scheme_raw = open(SCHEME).read() if os.path.exists(SCHEME) else ""
POL = sf.get("policies", []); ATT = sf.get("atts", []); QA = sf.get("qaSheets", []); TIX = sf.get("recertTickets", [])

# resume: keep bundles already built
bundles = {}
# Resume ONLY within the same day's run: if the SF cache is newer than the last
# bundle file, a fresh SF pull happened -> rebuild everything so all fields refresh.
if os.path.exists(OUT) and os.path.getmtime(OUT) >= os.path.getmtime(SF):
    try: bundles = json.load(open(OUT)).get("bundles", {})
    except Exception: bundles = {}
done = set(bundles.keys())
todo = [o for o in sf["opps"] if o["Id"] not in done]
if LIMIT: todo = todo[:LIMIT]
print("opps total %d | already done %d | to build %d | workers %d" % (len(sf["opps"]), len(done), len(todo), WORKERS))

lock = threading.Lock(); built = [0]; _t0 = time.time()
def build_one(o):
    oid=o["Id"]; acct=o["AccountId"]; date=o["Renewal_Date__c"]; dbefore=day_before(date)
    m=re.search(r"(\d+)\s*$", o.get("Source_ID__c") or ""); rid=int(m.group(1)) if m else None
    renPols=[p for p in POL if p["Account__c"]==acct and p["Coverage_Effective_Date__c"]==date]
    expPols=[p for p in POL if p["Account__c"]==acct and p["Expiration_Date__c"]==dbefore]
    d={"DATE":date,"DBEFORE":dbefore,"RID":str(rid) if rid else None,
       "acctName":o.get("Account",{}).get("Name"),
       "renPols":renPols,"expPols":expPols,"cOrders":[],
       "qaSheets":[q for q in QA if q["Opportunity__c"]==oid],
       "atts":[a for a in ATT if a["LinkedEntityId"]==oid],
       "recertTickets":[t for t in TIX if t["Opportunity__c"]==oid],
       "A":None,"B":None,"C":None,"D":[],"E":[],"F":[],"sheetErr":None}
    if rid:
        a=run_snow("A",rid,date,dbefore); b=run_snow("B",rid,date,dbefore); c=run_snow("C",rid,date,dbefore)
        d["A"]=a[0] if a else None; d["B"]=b[0] if b else None; d["C"]=c[0] if c else None
        d["D"]=run_snow("D",rid,date,dbefore); d["E"]=run_snow("E",rid,date,dbefore); d["F"]=run_snow("F",rid,date,dbefore)
        if d["C"]:  # 9A: drop raw street address, keep a presence flag (address is Snowflake-sourced)
            d["C"]["ADDR_STREET"]="On file — verify in Hippo"
            for k in ("ADDR_CITY","ADDR_STATE","ADDR_ZIP","FILING_STREET","FILING_CITY","FILING_STATE","FILING_ZIP"): d["C"][k]=None
            d["C"]["ADDR_MAIL_EQ_FILING"]=None
    return oid, {"o":o,"d":d}

def flush():
    with lock:
        tmp = OUT + ".tmp"
        json.dump({"bundles":bundles,"scheme":scheme_raw}, open(tmp,"w"), default=str)
        os.replace(tmp, OUT)   # atomic: a timeout-kill can never leave OUT half-written

with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs={ex.submit(build_one,o):o for o in todo}
    for fut in cf.as_completed(futs):
        try:
            oid,rec=fut.result(); 
            with lock: bundles[oid]=rec; built[0]+=1
            if built[0]%25==0:
                flush()
                print("  built %d/%d  (%.0fs elapsed)" % (built[0],len(todo),time.time()-_t0), flush=True)
        except Exception as e:
            print("  ERROR opp %s: %s" % (futs[fut].get("Id"), str(e)[:120]))
flush()
print("DONE. bundles now: %d (target opps: %d)" % (len(bundles), len(sf["opps"])))
