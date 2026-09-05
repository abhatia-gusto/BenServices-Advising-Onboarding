-- roster / PE map (bi.gusto_employees) — Broker Onboarding (BYB + BT), current snapshot
select name as NAME, pe as PE, sub_team as SUB_TEAM, is_pe as IS_PE
from bi.gusto_employees
where current_flag=true
  and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')
