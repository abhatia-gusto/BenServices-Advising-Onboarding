import json
from collections import defaultdict
import os as _os, datetime as _dt
_END=_os.environ.get("PERF_END") or _dt.date.today().isoformat()
def _mrange(sy,sm,ey,em):
    out=[];y,m=sy,sm
    while (y<ey) or (y==ey and m<=em):
        out.append(f"{y}-{m:02d}");m+=1
        if m>12:m=1;y+=1
    return out
MONTHS=_mrange(2026,1,int(_END[:4]),int(_END[5:7]))
# Footer dates: published = refresh/end date; data_through = last COMPLETE day (end - 1),
# since source SQLs run BETWEEN '2026-01-01' AND CURRENT_DATE() (today is only partial).
_ENDd=_dt.date.fromisoformat(_END)
_THRUd=_ENDd - _dt.timedelta(days=1)
_MN=['January','February','March','April','May','June','July','August','September','October','November','December']
_SH=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
_PUBLISHED=f"{_MN[_ENDd.month-1]} {_ENDd.day}, {_ENDd.year}"
_DATA_THROUGH=f"{_MN[_THRUd.month-1]} {_THRUd.day}, {_THRUd.year}"
_PERIOD=f"{_SH[int(MONTHS[0][5:7])-1]}–{_SH[int(MONTHS[-1][5:7])-1]} {MONTHS[-1][:4]}"
L=lambda f: json.load(open('data/'+f))
def num(x):
    try:return float(x)
    except:return 0.0
roster=L('roster.json'); bo=L('bo.json'); ts=L('ticketsla.json'); qa=L('qa.json'); ab=L('abandon.json'); av=L('avail.json')
abm={r['MONTH']:round(100*num(r['ABANDON'])/max(num(r['OFFERED'])+num(r['ABANDON']),1),2) for r in ab}
ab_agg=round(100*sum(num(r['ABANDON']) for r in ab)/max(sum(num(r['OFFERED'])+num(r['ABANDON']) for r in ab),1),2)
def norm(s): return (s or '').strip().lower()
def idx(rows):
    d=defaultdict(dict)
    for r in rows: d[norm(r['IC'])][r['MONTH']]=r
    return d
abic=L('abandon_ic.json')
csatr=L('csat_rows.json')
emailr=L('email_ic.json')
maestror=L('maestro_ic.json')
from collections import defaultdict as _dd
_cs=_dd(lambda:[0.0,0]);_cm=_dd(list);_em=_dd(lambda:[0,0]);_ma=_dd(lambda:[0,0])
for _r in csatr:
    _lk=norm(_r['IC']);_m=_r['MONTH']
    if _r['SCORE'] is not None:_cs[(_lk,_m)][0]+=float(_r['SCORE']);_cs[(_lk,_m)][1]+=1
    _c=(_r['COMMENT'] or '').strip()
    if _c:_cm[_lk].append({'s':int(_r['SCORE']),'d':_r['DT'],'c':_c})
for _r in emailr:
    _lk=norm(_r['IC']);_m=_r['MONTH'];_em[(_lk,_m)][0]+=int(_r['MET']);_em[(_lk,_m)][1]+=int(_r['TOTAL'])
for _r in maestror:
    _lk=norm(_r['IC']);_m=_r['MONTH'];_ma[(_lk,_m)][0]+=int(_r['MA_ADHERENT']);_ma[(_lk,_m)][1]+=int(_r['MA_ELIGIBLE'])
boi,tsi,qai,avi,abici=idx(bo),idx(ts),idx(qa),idx(av),idx(abic)

# union-from-data roster gate: roster.json now carries ALL statuses (q_roster widened).
# Include an IC iff currently Active/On Leave OR they have scored data in a shown month
# (former-but-worked). Preserves worked-months; month-aware auto-uncheck hides empties.
_ACTIVE_ST={'Active','On Leave'}
def _has_scored(lk):
    for _ix in (boi,tsi,qai,avi,abici):
        _d=_ix.get(lk)
        if _d and any(_m in _d for _m in MONTHS): return True
    return False

out=[]
_skipped=0
for r in roster:
    ic=r['NAME']; lk=norm(ic)
    if (r.get('STATUS') or '') not in _ACTIVE_ST and not _has_scored(lk):
        _skipped+=1; continue
    months={}
    for m in MONTHS:
        b=boi.get(lk,{}).get(m,{}); t=tsi.get(lk,{}).get(m,{}); q=qai.get(lk,{}).get(m,{}); av=avi.get(lk,{}).get(m,{})
        months[m]={
          'oa_n':num(b.get('OA_PASS_N')),'oa_d':num(b.get('OA_ELIG_N')),
          'nc_n':num(b.get('NP_CANCELS')),'nc_d':num(b.get('NP_ORDERS')),
          'tnp_n':num(b.get('NP_FUL_TKT')),'tnp_d':num(b.get('NP_FUL')),
          'trn_n':num(b.get('RN_FUL_TKT')),'trn_d':num(b.get('RN_FUL')),
          'tnp_s':num(b.get('NP_TKT_SUM')),'trn_s':num(b.get('RN_TKT_SUM')),
          'ts_n':num(t.get('CLOSED_5D')),'ts_d':num(t.get('N_TICKETS')),
          'qa_s':num(q.get('QA'))*num(q.get('N_QA')),'qa_n':num(q.get('N_QA')),
          'av_s':num(av.get('SLA_MET_DAYS')),'av_d':num(av.get('ELIG_DAYS')),
          'ab_n':num(abici.get(lk,{}).get(m,{}).get('ABANDONED_MOD')),'ab_d':num(abici.get(lk,{}).get(m,{}).get('INBOUND_CT')),
          'cs_s':_cs.get((lk,m),[0,0])[0],'cs_n':_cs.get((lk,m),[0,0])[1],'em_n':_em.get((lk,m),[0,0])[0],'em_d':_em.get((lk,m),[0,0])[1],
          'ma_n':_ma.get((lk,m),[0,0])[0],'ma_d':_ma.get((lk,m),[0,0])[1],
          'ord':num(b.get('ORDERS')),
        }
    av_sum=sum(num(avi.get(lk,{}).get(m,{}).get('SLA_MET_DAYS')) for m in MONTHS)
    av_days=sum(num(avi.get(lk,{}).get(m,{}).get('ELIG_DAYS')) for m in MONTHS)
    phone=round(100*av_sum/av_days,1) if av_days else None
    phone_m={m:(round(100*num(avi.get(lk,{}).get(m,{}).get('SLA_MET_DAYS'))/num(avi.get(lk,{}).get(m,{}).get('ELIG_DAYS')),1) if avi.get(lk,{}).get(m,{}).get('ELIG_DAYS') else None) for m in MONTHS}
    vol=int(sum(months[m]['ord'] for m in MONTHS))
    out.append({'name':ic,'team':r['SUB_TEAM'],'manager':r.get('MANAGER') or '—','vol':vol,
                'months':months,'phone':phone,'phone_m':phone_m,'comments':sorted(_cm.get(lk,[]),key=lambda x:x['d'],reverse=True)[:40]})

metrics_cfg=[
 {'key':'phone_avail','label':'Phone Availability','short':'Phone Avail.','bucket':'SLA Delivery','dir':'range','goal':80,'upper':105,'floor_pct':81.25,'fmt':'%','fullperiod':True},
 {'key':'abandon','label':'Abandon (mod.)','short':'Abandon','bucket':'SLA Delivery','dir':'lower','goal':5,'floor_pct':25,'fmt':'%','fullperiod':True},
 {'key':'ticket_sla','label':'Ticket SLA','short':'Ticket SLA','bucket':'SLA Delivery','dir':'higher','goal':80,'floor_pct':81.25,'fmt':'%'},
 {'key':'oa_held','label':'BO Status (OA Held)','short':'BO Status (OA Held)','bucket':'SLA Delivery','dir':'higher','goal':60,'floor_pct':66.66666666666667,'fmt':'%'},
 {'key':'qa','label':'Level AI QA','short':'Level AI QA','bucket':'Quality','dir':'higher','goal':90,'floor_pct':88.889,'fmt':'%'},
 {'key':'ticket_rate','label':'Ticket Rate','short':'Ticket Rate','bucket':'Quality','dir':'lower','goal':1.2,'goal_rn':0.37,'floor':1.5,'floor_rn':0.5,'fmt':'ratio','bytype':True},
 {'key':'np_cancel','label':'New Plan Cancel Rate','short':'NP Cancel','bucket':'Cancel','dir':'lower','goal':15,'floor_pct':50,'fmt':'%'},
]
abc={r['MONTH']:{'ab':num(r['ABANDON']),'off':num(r['OFFERED'])} for r in ab}
data={'published':_PUBLISHED,'data_through':_DATA_THROUGH,'period':_PERIOD,'months':MONTHS,
      'buckets':['SLA Delivery','Quality','Cancel'],'metrics':metrics_cfg,
      'abandon_monthly':abm,'abandon_agg':ab_agg,'abandon_counts':abc,'ics':out}
json.dump(data,open('oa_data.json','w'),separators=(',',':'))
print("wrote oa_data.json bytes:",len(open('oa_data.json').read()),"ICs",len(out),"| roster rows",len(roster),"| skipped(no status/no data)",_skipped)
