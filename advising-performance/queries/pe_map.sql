-- PE map: current PE per advisor. Wrap advising_opp_sla_v6_0 (opp_sla.sql) as src.
with src as ( /* paste opp_sla.sql body */ )
select owner_name as advisor,
       max_by(coalesce(pe_name, pe_name_at_close), close_date_computed) as pe
from src where owner_name is not null group by 1;
