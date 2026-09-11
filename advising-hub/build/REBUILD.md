# REBUILD.md — 1:1 rebuild spec for `build_advising_hub.py`

A section-by-section specification detailed enough to reconstruct `build_advising_hub.py` from scratch and get a byte-equivalent dashboard. Section numbers map to the code top-to-bottom. The canonical builder source is committed alongside this file as the single file `build/build_advising_hub.py` (git blob SHA `63fb706e0fbf3c06c6cfab09014012c5a01f4613`). The risk engine is also reproduced verbatim inside `build/refresh_advising_hub.py` (`RISK_JS`), which the pipeline uses to count at-risk-High during verify — keep the two in sync.

---

## 0. Program shape

- Single Python 3 script, no third-party imports: `import json, os, re, html as _html`.
- Paths (all relative to the script dir `HERE`): `DATA_PATH = HERE/_renewal_vnext/advising_vnext_data.json`; `GUIDE_PATH = HERE/Advising_Hub_README.md`; `OUT = HERE/advising_hub_vnext.html`.
- Load data: `data = json.load(open(DATA_PATH))`; `n_opps=len(data)`; `n_lines=sum(len(o.get("lines") or []) for o in data)`.
- Serialize: `data_json = json.dumps(data, separators=(",",":"))` then `data_json = data_json.replace("</","<\\/")` (so `</script>` can't close the embedding block).
- Emit model: one big Python raw-string `TEMPLATE = r"""...html..."""` containing the entire page with two placeholders `__GUIDEHTML__` and `__HUBDATA__`. Final 3 lines: `html = TEMPLATE.replace("__GUIDEHTML__", guide_html).replace("__HUBDATA__", data_json)`, `open(OUT,"w").write(html)`, and a `print(f"wrote {OUT} ({len(html)/1024:.0f} KB) opps={n_opps} lines={n_lines}")`.
- Single-file HTML: the data ships as `<script id="hubdata" type="application/json">__HUBDATA__</script>`; the app logic is one `<script>…</script>` right after it. No external JS/CSS except Google Fonts (Bricolage Grotesque + JetBrains Mono).
- The source is ~162 KB / ~2,340 lines, committed as the single file `build/build_advising_hub.py` (git blob SHA `63fb706e0fbf3c06c6cfab09014012c5a01f4613`; earlier revisions stored it as byte-exact slices under `build/_builder_src/`, now retired).

## 1. `md_to_html(md)` + Read Me injection

Minimal Markdown→HTML for the Read Me pane. Supports: `#`/`##`/`###` headings, `**bold**`, `` `code` ``, `-`/`*` bullet lists (`<ul><li>`), `---` horizontal rules, and paragraphs; HTML-escapes text first (`_html.escape`), then applies bold/code regexes. Line loop with `flush_para()`/`close_ul()` helpers. `guide_html = md_to_html(open(GUIDE_PATH).read()) if exists else "<p>Guide unavailable.</p>"`, injected into the `#pane-guide .guidedoc` via `__GUIDEHTML__`.

## 2. `<head>` / CSS (`:root` variables + group band colors)

`:root` custom properties (light color-scheme). Key tokens: `--teal:#4f46e5` (indigo, the primary), `--teal-dk:#3730a3`, `--teal-tint:#e0e7ff`, `--teal-050:#eef0fe`, `--coral:#F45D48`, `--coral-dk:#993C1D`, `--coral-20:#fde3de`, `--ink:#222525`, greys `--g6..--g2`, `--gold:#b8860b`, `--green:#1D9E75`, `--slate:#334155`, `--slate-chip:#64748b`, `--plum:#7c3a6e`, `--bg:#F7F4F2`, `--card:#FFFFFF`, `--line:#e5e7eb`; `--ui` = Bricolage Grotesque stack, `--mono` = JetBrains Mono.

**Group header band colors** (`tr.grp th.g-*`): `g-customer`→`--slate`; `g-queue`→`--slate-chip`; `g-general`→`--teal`; `g-line`→`--teal`; `g-flags`→`--coral`; `g-contact`→`--teal-dk` (a `#3f6fa3` rule appears earlier but is overridden by the later `--teal-dk` rule — keep both lines in order); `g-sentiment`→`--green`; `g-rec`→`--gold`; `g-closed`→`--coral-dk`; `g-bo`→`--plum`.

Other notable CSS: sticky `thead` (`tr.grp th{top:0}`, `tr.cols th{top:26px}`); pinned left columns `th.pin,td.pin{position:sticky}` with z-index layering and a `.shadow` right-edge; tier chips `.tier.t1..t5`; risk chips `.rsc-hi`(coral)/`.rsc-med`(gold)/`.rsc-lo`(green)/`.rsc-arch`(slate-chip); LF savings pills; dots; threshold text classes `.t-bad`/`.t-warn`/`.t-gold`/`.t-ok`; synced scrollbars; drill `.kv` grid, `.summ` callout, `table.lines`/`table.mini`, `.tl` timeline; Customer Positioning `.doc .*` styles; Overview `.ov-*` styles. The Book-insights pct+count variant uses `.ov-ins-rowc` (a two-line block: label + `%` on the main row via `.ov-ins-v.num-col`, and the raw opp count on its own muted sub-row `.ov-ins-cntrow`, right-aligned).

## 3. `<body>` skeleton

- `.head`: brand "Benefits Advising **Hub**" + `<span class="verbadge">alpha</span>`, subtitle, and a right-aligned `#cohortPill` chip.
- `.tabs`: six buttons with `data-pane`: **overview** (starts `on`), **open**, **pf**, **closed**, **script** ("Customer Positioning"), **guide** ("Read Me").
- Panes: `#pane-overview` (`#ovScope` + `#ovBody`); `#pane-table` (starts `on`) with `#kpis`, a `.bar` of filter mounts (`#fSearch`, `#mdAdv`, `#mdPE`, `#mdStage`, `#mdTier`, `#mdCohort`, `#mdRisk`), synced `#tblTop`/`#tblwrap` scrollers, `<table id="tbl">` with `#grpRow`+`#hdr` in thead and `#body` tbody, and `#foot`; `#pane-script`; `#pane-guide` (`.guidedoc` = `__GUIDEHTML__`).

## 4. App bootstrap + per-row derivations

- `const HUB = JSON.parse(document.getElementById("hubdata").textContent)`.
- `TODAY = new Date(new Date().toISOString().slice(0,10)+"T00:00:00")`.
- `TAB_CLOSED = new Set(["Closed Won","Closed Lost","Order Lost","Closed Admin"])`.
- State globals: `PAGE=1`, `PAGE_SIZE=100`, `TAB="open"`, `CLOSED=false`, `SORT={k:"tier",dir:1}`, `OPEN=null`, `LINES_OPEN=false`, `DRILL_SORT={k:"enr_before",dir:-1}`, `LS_KEY="advhub_state_v1"`.
- `tabOf(r)`: `TAB_CLOSED.has(stage)?"closed":(stage==="Pending Fulfillment"?"pf":"open")`.
- `HUB.forEach`: strip trailing `*` from `advisor`/`pe`; derive `cohort` from `renewal_date` (`YYYY-MM`); compute **`queue_tier`** (Outreach priority) — collect flags then `Math.min`: **P1 if `default_automation==="Y"`** (Default Automation — recs auto-sent, customer-outreach priority); P2 if `lf_quote && lf_savings_band && band!=="No"`; P3 if `rate_increase_pct>=15 && rate_status && not /^estimate/`; P4 if `!enrollees || !mrr`; P5 if `selection_deadline`; default 5. Also `tier_annos` (descriptive only).

## 5. Column model (GROUPS + every column)

Utility: `medLine(r)` = the `lines[]` entry with `benefit_type==="medical"`; `PIN_W = {company:210, advisor:132, pe:120}`. `BASE_COLS` in order, `{k,g,t,s,tabs,ttl}`:

- **customer**: `company` (pin, links + icons), `advisor` (pin), `pe` (pin).
- **queue** (= "Outreach priority"): `tier` (`s:queue_tier`), `risk` (`s:riskCached(r).score`).
- **closed** (`tabs:"c"`): `outcome`, `closedon`, `mrrb`, `mrra`.
- **general**: `renewal`, `survey`, `seldl`, `subdl`, `d2r`, `d2s`, `lead`, `stage`, `dis`, `mrr` (`tabs:"op"`), `funding`, `enr`, `carrier`, `packets`, `rate` (title fn → Final on closed else Projected).
- **line**: `nlines`; the per-benefit `LINE_COLS` (`ln_<bt>`) splice in after `nlines`.
- **flags**: `lf`, `lfsav`, `recert`, `sep`, `bor`, `autoren`, `defauto`.
- **contact** (= "Customer Contact"): `intro`, `introc` (Intro Connect), `emaildue` (`tabs:"op"`), `emailrecv` (`tabs:"op"`), `lastout` (Last email out), `lastin` (Last email in), `lastupd` (**"Last call"** — sorts on `last_call_date`; renders `M/D · disp` with disp = connect/VM/attempt from `last_call_disp`).
- **sentiment**: `survcount` (`tabs:"o"`), `inapp` (`tabs:"pc"`), `csat` (`tabs:"c"`).
- **rec**: `recsent`, `d2def`, `trfd`, `altreq`, `altcreated`, `altpub`, `days2alt`, `terc`.
- **bo** (`tabs:"pc"`): `tix`, `opentix`, `opentixsla`, `bostatus` (last on PF/Closed).

**Cell formatting / color rules** (`cell(r,k)`): `tier` → live `tierChip` on Open, greyed `.chip.arch` on PF/Closed. `risk` → `.rsc` chip colored by tier + top reasons. `rate` → `%` with `t-gold` ≥15, `t-warn` ≥20, `t-bad` ≥30. `lastout` days-ago `t-bad` >14 / `t-warn` >7; `lastin` `t-bad` >21 / `t-warn` >14. `lastupd` shows the last call date + disposition tag. Blank → `DASH`.

## 6. RISK MODELS (verbatim)

Constants: `EARLY = {"Open","SAL","Attempting Contact","New","Working","Nurturing"}`; `MID = {"Engaged","ER Confirm"}`; `_daysSince(s)=-dUntil(s)`.

**`riskOpen(r)`** — pushes `{key,w,sev,reason}` signals. The three "gone quiet" recency signals are **binary and weight 0** — they don't add to the numeric score; instead they drive the tier via the floor override in `riskOf` (§below). All others are weighted EYO-2 signals:
1. `unworked` w15: `early=EARLY?1:MID?0.5:0`; `sev = early*(dtr==null?0.2 : dtr<=30?1 : dtr<=45?0.8 : dtr<=60?0.5 : 0.2)`.
2. `termbor` w15: `/Pending Termination|BoR Away/i`→1; `/BoR Incomplete/i`→0.7; else 0.
3. **`silence` w0 (gone-quiet #1)** on `last_outbound_email_date`: `sev = 1` if `_daysSince>21` **or null** (never emailed), else 0.
4. `rate` w12 on `rate_increase_pct`: ≥30→1; ≥20→0.6; ≥15→0.3; else 0.
5. **`noresp` w0 (gone-quiet #2)** on `last_inbound_email_date`: `sev = 1` if `_daysSince>21` **or null**, else 0.
6. **`callconnect` w0 (gone-quiet #3)** on `last_connect_date`: `sev = 1` if `_daysSince>21` **or null**, else 0.
7. `lategen` w10 on `lead_days`: <60→1; <75→0.5; else 0.
8. `stagnant` w10 on `days_in_stage`: >21→1; >14→0.66; >7→0.33; else 0.
9. `nointro` w10: `isY(intro_call)?0:1`.
10. `deadline` w10 on `dUntil(selection_deadline)`: <0→1; ≤7→0.6; ≤14→0.3; else 0.
11. `subdl` w10 on `dUntil(submission_deadline)`: same mapping.
12. `packet` w8: `/Packet Needed/i`→1; else `((packets_files==0||null)&&packet_carriers)?0.4:0`.
13. `altsla` w8: only if `alt_requested_date`; `gap = alt_published_date?days_to_alt:_daysSince(alt_requested_date)`; `>3→1, ==3→0.5, else 0`.
14. `recert` w8 on `recert_lateness_days`: >60→1, >30→0.7, >14→0.4, >0→0.25; else (recert_ticket|recert_status|/recert/ in blocked)→0.5 else 0.
15. `lfpend` w6: `band∈{High,Medium,Low}` and `lf_in_alt!=="Y"` → High1/Med0.7/Low0.4; else 0.
16. `sepgr` w6: `isY(sep)?1:0`.
`WTOTAL_OPEN=128`; `score=round(100*Σ(w·sev)/128)`. `goneQuiet` = count of {silence,noresp,callconnect} with sev>0 (0–3). `firing`=sev>0 sorted by `w·sev` desc (the weight-0 recency signals still appear in `firing`/`reasons` so the drill can list them); returns `{score, reasons, firing, goneQuiet}`.

**`riskPF(r)`** — 5 factors (unchanged): `sentiment` w30, `ticket` w30 (`tickets_to_advising`), `recert` w20, `within1wk` w30 (`dUntil(submission_deadline)` 0–7→1 / 8–14→0.5), `autoren` w20 (`isY(auto_renewal)`× rate band). `WTOTAL_PF=130`.

**`riskOf(r)`**: open→riskOpen; pf→riskPF; closed→riskPF with `archived=true`. Base `tier = score>=35?"High" : score>=18?"Med" : "Low"`. **Gone-quiet floor override (Open only):** `floor = goneQuiet>=3?"High" : goneQuiet>=1?"Med" : "Low"`; `tier = max(score-tier, floor)` by rank {Low:0,Med:1,High:2}. So 3-of-3 quiet forces at least High, 1–2 at least Med, and substantive weighted risk can still raise (never lower) the tier. **`riskCached(r)`** memoizes on `r.__risk`.

## 7. KPIs

`renderKpis()` over `filtered()`: "Opps" count; MRR cards (before/after on Closed, else "MRR (before)"); final `kpi accent` "At risk (High)" = count where `riskCached.tier==="High"`.

## 8. Filters (SEL sets + `multiDrop` + risk multi-select)

`SEL = {adv,pe,stage,tier,cohort,risk}` (Sets). `multiDrop(mountId,label,items,sel,onChange)` builds a checkbox dropdown (summary, All/None, search, grouped list). `buildFilters()` seeds adv/pe/stage/tier/cohort to ALL; Risk drop = fixed `[High, Med, Low]` seeded ALL. `filtered()` = current tab AND adv/pe/stage membership AND (`queue_tier==null` OR tier membership) AND cohort AND `SEL.risk.has(riskCached(r).tier)` AND free-text over company+advisor+pe.

## 9. View-state persistence

`serializeState()` captures tab/sort/page/pageSize/search/risk/sel-arrays. `persist()` → `localStorage[LS_KEY]` + `history.replaceState("#advhub=<encoded>")`. `restoreState()` reads hash first, else localStorage; validates.

## 10. Table render + pagination

`render()`: `renderKpis()`; `visibleCols()`; group band row + `#hdr` column row (sort arrows, tooltips). Header click sets `SORT` (whitelist sorts ascending first; others descending), resets PAGE=1. Sort the FULL `filtered()` via `col.s` null-last + company tiebreak. **Pagination = filter→sort→slice**: only the current page's rows enter the DOM; the open drill row appends. Footer = rows-per-page (50/100/250), Prev/Next, page jump, "Showing a–b of N (filtered from M)".

## 11. Drill-down (`detailRow`)

Row click toggles `OPEN`; sections in order: Overall case summary → Renewal-cycle timeline → General → Customer Contact (intro/connect, last email out/in with "Nd ago", **Last call (date · disposition · Nd ago) + Last connect**, email awaiting reply) → Survey answers → Premium & lines → Flags → Recommendation → Sentiment → Benefit order. A highlighted **risk "why"** line sits at the top: Open groups firing signals into 4 clusters (Customer connection = nointro/silence/noresp/callconnect; Minimal SF update = stagnant; Recommendation = rate/altsla/lfpend; Flags = termbor/sepgr/recert/packet/deadline/subdl/unworked/lategen) and, when the gone-quiet floor set the tier above the weighted score, prepends `Tier set to <tier> by "gone quiet" (<n> of 3 channels: no email 21d+, no reply, no connect).`; PF/Closed render a flat "Driven by …" (Closed prefixed "Archived — "). If no signals fire, an all-clear sentence shows.

## 12. Customer Positioning talk track (`buildScript`)

`TIER_NAMES` = {1:"Default Automation", 2:"Level-funded available", 3:"Above-market rate", 4:"Data gap", 5:"Selection deadline"}. `F(v)` = filled indigo, `PH(v)` = placeholder. `buildScript(r)` toggles conditional modules, prep table, flow bar, 7 numbered beats, objection handling, voicemail scripts, Do/Don't grid. `.doc.sampleonly` hides all but sample lines. Footer states no customer PII is surfaced.

## 13. Overview tab

State: `OVSCOPE={mode:"team",peSel,icSel}`, `OVSTAGE`, `OVRISK={open,pf}`. `OV_HI="#c0392b"`, `OV_MED="#e0a83e"`, `OV_LO="#5aa87f"`. `ovStageCards(g)` = 3 clickable tiles. `ovInsights(L,O)` = "Book insights" 5-column strip, where `L` = live (open+pf), `O` = open:
- **OUTREACH**: intro complete %, connect rate, email due, **Email outside SLA** (`rowc`: % + count sub-row), outreach pending (no rec).
- **CONTACT ≤21d (share reached · median age)**: for each channel the share of `L` reached within 21 days (`within21(f)` = pct with `daysSince(f)!=null && <=21`) with the median age on the muted sub-row (`medAge`): **Emailed out**, **Customer reply in**, **Connected (call)**. These are the positive mirror of the three gone-quiet risk signals.
- **RECOMMENDATION & SLA**: default rec sent %, days-to-default, time in RFD/ERC, RFD/ERC/ALT/Ticket **outside SLA** (`rowc`, na-excluded), **Alt requested** and **Alt published** (`rowc`, each % of all live L with count sub-row), avg alt packages, days-to-alt.
- **PREMIUM (medical)**: median Δ (excludes no-rate opps), **≥15%**, **≥20%** — both computed as **% of the whole live book** (all Open+PF, including the ~4% with no rate data), NOT only customers with a rate change.
- **FLAGS**: LF available %, auto-renewal %, default automation %, recert open, packet needed, BoR/Term.

`ovRiskOpenTiers(O)` = P1–P5 bars (red overlay = High). `ovRiskTierBox(rows,title,boxKey,LABELMAP)` = High/Med/Low bars with an expandable "what's driving it" factor panel. `ovRollup()` = PE-team / IC table (LIVE OPPS / OPEN HIGH / PF HIGH / AT-RISK TOTAL + a compact OUTSIDE SLA % cell). `ovDrill()` applies scope + tier/risk to the grid `SEL`s and `showTab(tab)`.

## 14. Tabs + init (`showTab`)

`showTab(name)` toggles `.tab.on`, shows one pane; data tabs set `TAB`/`CLOSED`, reset `OPEN`/`PAGE`, swap default sort between `{tier,1}` and `{closedon,-1}`. Init: wire tab clicks, script buttons, sample toggle, `#fSearch`, synced scroll lock, delegated `#body` click; then `buildFilters(); buildScriptSearch(); restoreState();` `render()`; `showTab("overview")` (default landing).

## 15. Color thresholds (quick reference)

Premium Δ / rate: **≥15% gold, ≥20% orange (`t-warn`), ≥30% red (`t-bad`)** — grid cell, drill headline, per-line table; Overview premium insights report **≥15%** / **≥20%** as **% of the whole live book**. Deadlines: past→`t-bad`, ≤7d→`t-warn`. Grid aging cells: outbound email >14/>7, inbound >21/>14. Overview CONTACT panel + all three gone-quiet **risk** signals use the **21-day** threshold (null counts as quiet). Days-in-stage >21/>14. Tickets: ≥2 warn (tix), ≥1 warn/bad. Risk tiers: score High ≥35 / Med ≥18 / Low; **plus** the Open gone-quiet floor (3 quiet→High, 1–2→Med).
