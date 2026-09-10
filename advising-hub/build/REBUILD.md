# REBUILD.md — 1:1 rebuild spec for `build_advising_hub.py`

A section-by-section specification detailed enough to reconstruct `build_advising_hub.py` from scratch and get a byte-equivalent dashboard. Section numbers map to the code top-to-bottom. The canonical builder source is committed alongside this file as ordered part files under `build/_builder_src/` (concatenate in name order → byte-identical to the original; git blob SHA `d95895beb0b2e052625c73c7cec3597836f60773`). The risk engine is also reproduced verbatim inside `build/refresh_advising_hub.py` (`RISK_JS`).

---

## 0. Program shape

- Single Python 3 script, no third-party imports: `import json, os, re, html as _html`.
- Paths (all relative to the script dir `HERE`): `DATA_PATH = HERE/_renewal_vnext/advising_vnext_data.json`; `GUIDE_PATH = HERE/Advising_Hub_README.md`; `OUT = HERE/advising_hub_vnext.html`.
- Load data: `data = json.load(open(DATA_PATH))`; `n_opps=len(data)`; `n_lines=sum(len(o.get("lines") or []) for o in data)`.
- Serialize: `data_json = json.dumps(data, separators=(",",":"))` then `data_json = data_json.replace("</","<\\/")` (so `</script>` can't close the embedding block).
- Emit model: one big Python raw-string `TEMPLATE = r"""...html..."""` containing the entire page with two placeholders `__GUIDEHTML__` and `__HUBDATA__`. Final 3 lines: `html = TEMPLATE.replace("__GUIDEHTML__", guide_html).replace("__HUBDATA__", data_json)`, `open(OUT,"w").write(html)`, and a `print(f"wrote {OUT} ({len(html)/1024:.0f} KB) opps={n_opps} lines={n_lines}")`.
- Single-file HTML: the data ships as `<script id="hubdata" type="application/json">__HUBDATA__</script>`; the app logic is one `<script>…</script>` right after it. No external JS/CSS except Google Fonts (Bricolage Grotesque + JetBrains Mono).

## 1. `md_to_html(md)` + Read Me injection

Minimal Markdown→HTML for the Read Me pane. Supports: `#`/`##`/`###` headings, `**bold**`, `` `code` ``, `-`/`*` bullet lists (`<ul><li>`), `---` horizontal rules, and paragraphs; HTML-escapes text first (`_html.escape`), then applies bold/code regexes. Line loop with `flush_para()`/`close_ul()` helpers. `guide_html = md_to_html(open(GUIDE_PATH).read()) if exists else "<p>Guide unavailable.</p>"`, injected into the `#pane-guide .guidedoc` via `__GUIDEHTML__`.

## 2. `<head>` / CSS (`:root` variables + group band colors)

`:root` custom properties (light color-scheme). Key tokens: `--teal:#4f46e5` (indigo, the primary), `--teal-dk:#3730a3`, `--teal-tint:#e0e7ff`, `--teal-050:#eef0fe`, `--coral:#F45D48`, `--coral-dk:#993C1D`, `--coral-20:#fde3de`, `--ink:#222525`, greys `--g6..--g2`, `--gold:#b8860b`, `--green:#1D9E75`, `--slate:#334155`, `--slate-chip:#64748b`, `--plum:#7c3a6e`, `--bg:#F7F4F2`, `--card:#FFFFFF`, `--line:#e5e7eb`; `--ui` = Bricolage Grotesque stack, `--mono` = JetBrains Mono.

**Group header band colors** (`tr.grp th.g-*`): `g-customer`→`--slate`; `g-queue`→`--slate-chip`; `g-general`→`--teal`; `g-line`→`--teal`; `g-flags`→`--coral`; `g-contact`→`--teal-dk` (a `#3f6fa3` rule appears earlier but is overridden by the later `--teal-dk` rule — keep both lines in order); `g-sentiment`→`--green`; `g-rec`→`--gold`; `g-closed`→`--coral-dk`; `g-bo`→`--plum`.

Other notable CSS: sticky `thead` (`tr.grp th{top:0}`, `tr.cols th{top:26px}`); pinned left columns `th.pin,td.pin{position:sticky}` with z-index layering and a `.shadow` right-edge; tier chips `.tier.t1..t5` (t1 coral, t2/t4 teal, t3 gold, t5 slate-chip); risk chips `.rsc-hi`(coral)/`.rsc-med`(gold)/`.rsc-lo`(green)/`.rsc-arch`(slate-chip); LF savings pills `.lfsav.lfs-hi/md/lo/no`; dots `.dot(.on/.warn/.bad)`; threshold text classes `.t-bad`(coral-dk), `.t-warn`(#8a5a00), `.t-gold`(gold), `.t-ok`(grey); synced scrollbars `.tbltop`+`.tblwrap`; drill `.kv` two-column grid, `.summ` callout, `table.lines`/`table.mini`, `.tl` timeline; Customer Positioning `.doc .*` styles incl. `.doc.sampleonly …{display:none}` (strips everything but sample lines); Overview `.ov-*` styles.

## 3. `<body>` skeleton

- `.head`: brand "Benefits Advising **Hub**" + `<span class="verbadge">alpha</span>`, subtitle "Renewal Workbench & Customer Outreach Platform · all 2026 cohorts (7/1–12/1)", and a right-aligned `#cohortPill` chip ("All cohorts").
- `.tabs`: six buttons with `data-pane`: **overview** (starts `on`), **open** (`#cnt-open`), **pf** (`#cnt-pf`), **closed** (`#cnt-closed`), **script** ("Customer Positioning"), **guide** ("Read Me").
- Panes: `#pane-overview` (`#ovScope` + `#ovBody`); `#pane-table` (starts `on`) with `#kpis`, a `.bar` of filter mounts (`#fSearch`, `#mdAdv`, `#mdPE`, `#mdStage`, `#mdTier`, `#mdCohort`, `#mdRisk`), synced `#tblTop`/`#tblwrap` scrollers, `<table id="tbl">` with `#grpRow`+`#hdr` in thead and `#body` tbody, and `#foot`; `#pane-script` (scriptbar with back/generic buttons, `#scriptSearch`+`#scriptCompanies` datalist, `#scriptWho`, sample-only toggle, `#scriptDoc`); `#pane-guide` (`.guidedoc` = `__GUIDEHTML__`).

## 4. App bootstrap + per-row derivations

- `const HUB = JSON.parse(document.getElementById("hubdata").textContent)`.
- `TODAY = new Date(new Date().toISOString().slice(0,10)+"T00:00:00")`.
- `TAB_CLOSED = new Set(["Closed Won","Closed Lost","Order Lost","Closed Admin"])`.
- State globals: `PAGE=1`, `PAGE_SIZE=100`, `TAB="open"`, `CLOSED=false`, `SORT={k:"tier",dir:1}`, `OPEN=null`, `LINES_OPEN=false`, `DRILL_SORT={k:"enr_before",dir:-1}`, `LS_KEY="advhub_state_v1"`.
- `tabOf(r)`: `TAB_CLOSED.has(stage)?"closed":(stage==="Pending Fulfillment"?"pf":"open")`.
- `HUB.forEach`: strip trailing `*` from `advisor`/`pe`; derive `cohort` from `renewal_date` (`YYYY-MM`); compute **`queue_tier`** (Outreach priority) — collect flags then `Math.min`: P1 if `default_rec_sent`; P2 if `lf_quote && lf_savings_band && band!=="No"`; P3 if `rate_increase_pct>=15 && rate_status && not /^estimate/`; P4 if `!enrollees || !mrr`; P5 if `selection_deadline`; default 5. Also `tier_annos` (descriptive only, do not change tier): "SEP" (sep==="Y"), "Recertification" (recert_ticket==="Y" or /recert/ in recert_status), "Renewal packet needed" (/packet/ in blocked_reason), "Estimated increase" (/^estimate/ in rate_status).

## 5. Column model (GROUPS + every column)

Utility: `medLine(r)` = the `lines[]` entry with `benefit_type==="medical"`; `lineEnr/lineEnrA` = per-line `enr_before/after`. `BT_DEFS` = medical/dental/vision/life/STD/LTD; `BT_PRESENT` filters to those actually present in data. `PIN_W = {company:210, advisor:132, pe:120}`. `nn=v=>v==null?-1:v`.

`BASE_COLS` in order, `{k,g,t,s,...}` (`g`=group, `t`=title (string or fn), `s`=sort accessor, `tabs`=which of `o`/`p`/`c` show it, `ttl`=header tooltip fn):

- **customer**: `company` (pin, links to `sf_opp_url`, icons), `advisor` (pin), `pe` (pin).
- **queue** (= "Outreach priority"): `tier` (`s:queue_tier`), `risk` (`s:riskCached(r).score`).
- **closed** (= "Closed-only", `tabs:"c"`): `outcome`, `closedon`, `mrrb` (MRR before), `mrra` (MRR after).
- **general**: `renewal` (Renewal date), `survey` (Survey answered), `seldl` (Selection deadline), `subdl` (Submission deadline), `d2r` (Days to Renewal), `d2s` (Days to Submission), `lead` (Lead days), `stage`, `dis` (Days in Stage), `mrr` (`tabs:"op"`), `funding`, `enr` (ENR med), `carrier` (Carrier med), `packets`, `rate` (title fn → "Premium Δ (Final)" on closed else "(Projected)"; `s` = closed→medLine.d_fin else rate_increase_pct; tooltip per tab).
- **line**: `nlines` ("Lines ▸"). The per-benefit `LINE_COLS` (`ln_<bt>`, `line:true`) are spliced in immediately AFTER `nlines`.
- **flags**: `lf` (LF), `lfsav` (LF savings; sort High4/Med3/Low2/No1/-1), `recert`, `sep`, `bor` (BoR/Term), `autoren` (Auto-renewal), `defauto` (Default automation).
- **contact** (= "Customer Contact"): `intro` (Intro done), `introc` (Intro Connect), `emaildue` (Email due, `tabs:"op"`), `emailrecv` (Received, `tabs:"op"`), `lastout` (Last email out), `lastin` (Last email in), `lastupd` (Last Update).
- **sentiment**: `survcount` (Surveys 12mo, `tabs:"o"`), `inapp` (In-app, `tabs:"pc"`), `csat` (CSAT, `tabs:"c"`).
- **rec** (= "Recommendation"): `recsent` (Default rec sent), `d2def` (Time to rec sent), `trfd` (Time in RFD), `altreq` (Alt requested), `altcreated` (Alt created), `altpub` (Alt published), `days2alt` (Days to alt), `terc` (Time in ERC).
- **bo** (= "Benefit order", `tabs:"pc"`): `tix` (Tickets → Advising), `opentix` (Open tickets), `opentixsla` (Open >5d), `bostatus` (BO status — MUST remain last on PF/Closed).

`COLS` = BASE_COLS with `LINE_COLS` inserted after `nlines`. `GROUP_LABEL` maps group keys → display names (customer, Outreach priority, Closed-only, General, Line (current), Flags, Customer Contact, Sentiment, Recommendation, Benefit order). `tabCode()`→`o|p|c`; `colInTab(c)` honors `c.tabs`; `visibleCols()` = COLS filtered by `LINES_OPEN` (line cols only when expanded) and current tab.

**Cell formatting / color rules** (`cell(r,k)` switch): `ln_*` → `enr_before`, or `before→after` on closed. `tier` → live `tierChip` on Open, greyed `.chip.arch` (last value) on PF/Closed. `risk` → `.rsc` chip colored by tier + top-3 reasons. `rate`/`rateCell` → `%` with color class **`t-gold` ≥15, `t-warn` ≥20, `t-bad` ≥30** (Closed uses `medLine.d_fin`, else `rate_increase_pct` with `rate_status` suffix, `est …` for estimates). `seldl`/`subdl`/`d2s` → `t-bad` if past, `t-warn` if ≤7d. `d2r` → `t-bad` ≤30, `t-warn` ≤45. `dis` → `t-bad` >21, `t-warn` >14. `lastout` → days-ago `t-bad` >14 / `t-warn` >7; `lastin` → `t-bad` >21 / `t-warn` >14. `lf`→"LF" badge; `lfsav`→`.lfsav` band pill + `lf_savings_pct`. `sep`/`bor`→red dot; `autoren`/`defauto`/`intro`/`introc`→on/ warn dots. `tix`→`t-warn` if ≥2; `opentix`→`t-warn` ≥1; `opentixsla`→`t-bad` ≥1. `trfd`/`terc`→`t-warn` >5. Money via `money()` (rounded `$`). Blank everywhere → `DASH` = `<span class="t-ok">—</span>`.

## 6. RISK MODELS (verbatim)

Constants: `EARLY = {"Open","SAL","Attempting Contact","New","Working","Nurturing"}`; `MID = {"Engaged","ER Confirm"}`; `_daysSince(s)=-dUntil(s)`.

**`riskOpen(r)`** — pushes `{key,w,sev,reason}` signals (Open EYO 2 model, tickets intentionally excluded):
1. `unworked` w15: `early=EARLY?1:MID?0.5:0`; `sev = early*(dtr==null?0.2 : dtr<=30?1 : dtr<=45?0.8 : dtr<=60?0.5 : 0.2)`.
2. `termbor` w15: `/Pending Termination|BoR Away/i`→1; `/BoR Incomplete/i`→0.7; else 0.
3. `silence` w12 on `last_outbound_email_date`: null→0.75; >14→1; >7→0.5; >4→0.25; else 0.
4. `rate` w12 on `rate_increase_pct`: null→0; ≥30→1; ≥20→0.6; ≥15→0.3; else 0.
5. `noresp` w10 on `last_inbound_email_date`: null→(outbound?0.8:0.4); >21→1; >14→0.6; >7→0.3; else 0.
6. `lategen` w10 on `lead_days`: null→0; <60→1; <75→0.5; else 0.
7. `stagnant` w10 on `days_in_stage`: null→0; >21→1; >14→0.66; >7→0.33; else 0.
8. `nointro` w10: `isY(intro_call)?0:1`.
9. `deadline` w10 on `dUntil(selection_deadline)`: null→0; <0→1; ≤7→0.6; ≤14→0.3; else 0.
10. `subdl` w10 on `dUntil(submission_deadline)`: same mapping.
11. `packet` w8: `/Packet Needed/i`→1; else `((packets_files==0||null)&&packet_carriers)?0.4:0`.
12. `altsla` w8: only if `alt_requested_date`; `gap = alt_published_date?days_to_alt:_daysSince(alt_requested_date)`; `>3→1, ==3→0.5, else 0`.
13. `recert` w8 on `recert_lateness_days`: >60→1, >30→0.7, >14→0.4, >0→0.25; else (recert_ticket|recert_status|/recert/ in blocked)→0.5 else 0.
14. `lfpend` w6: `band∈{High,Medium,Low}` and `lf_in_alt!=="Y"` → High1/Med0.7/Low0.4; else 0.
15. `sepgr` w6: `isY(sep)?1:0`.
`WTOTAL_OPEN=150`; `score=round(100*Σ(w·sev)/150)`; `firing`=sev>0 sorted by `w·sev` desc; `reasons`=firing reasons.

**`riskPF(r)`** — 5 factors:
1. `sentiment` w30: `cur = in_app_date && cycle_open && in_app_date>=cycle_open`; `ia=parseFloat(inapp_current)`; `cmt=!!in_app_comment`; `sev = (cur&&(!isNaN(ia)||cmt)) ? (ia<=2?1 : ia<=3?0.7 : (cmt?0.7:0)) : 0`.
2. `ticket` w30 on `tickets_to_advising`: ≥3→1; ==2→0.7; ==1→0.4; else 0.
3. `recert` w20: `recert_status && !=="Recert Approved" ?1:0`.
4. `within1wk` w30 on `dUntil(submission_deadline)`: 0–7→1; 8–14→0.5; else 0.
5. `autoren` w20: `isY(auto_renewal)? (inc>=20?1 : inc>=14?0.6 : 0.3) : 0` (`inc=rate_increase_pct`).
`WTOTAL_PF=130`; `score=round(100*Σ/130)`.

**`riskOf(r)`**: open→riskOpen; pf→riskPF; closed→riskPF with `archived=true`. `tier = score>=35?"High" : score>=18?"Med" : "Low"`. **`riskCached(r)`** memoizes on `r.__risk`.

## 7. KPIs

`renderKpis()` over `filtered()`: card 1 "Opps" = row count; then MRR — on Closed two cards "MRR before"/"MRR after" (sum `mrr_before`/`mrr_after`), else one "MRR (before)" (sum `mrr_before`); final `kpi accent` "At risk (High)" = count where `riskCached.tier==="High"`. `.kpi tealk` for MRR (mono), `.kpi accent` for risk.

## 8. Filters (SEL sets + `multiDrop` + risk multi-select)

`SEL = {adv,pe,stage,tier,cohort,risk}` (Sets). `multiDrop(mountId,label,items,sel,onChange)` builds a checkbox dropdown: trigger with summary ("All"/"None"/label/"N selected"), All/None buttons, a search box, and a grouped list ("Selected (n)" first). Closes on outside mousedown. `buildFilters()` seeds adv/pe/stage/tier/cohort to ALL from HUB (tier items = distinct `queue_tier` as `P#`; cohort labels via `cohortLabel`), wires `onChange = ()=>{OPEN=null;PAGE=1;persist();render();}`, and builds the Risk drop from fixed items `[High, Medium(Med), Low]` seeded ALL. `filtered()` = `rows()` (current tab) AND adv/pe/stage membership AND (`queue_tier==null` OR tier membership) AND cohort membership AND `SEL.risk.has(riskCached(r).tier)` AND free-text search over company+advisor+pe.

## 9. View-state persistence

`serializeState()` captures tab/sort/page/pageSize/search/risk/sel-arrays. `persist()` → `localStorage[LS_KEY]` + `history.replaceState("#advhub=<encoded>")`. `restoreState()` reads the hash first, else localStorage; validates tab∈{open,pf,closed}, pageSize∈{50,100,250}, etc.

## 10. Table render + pagination

`render()`: `renderKpis()`; compute `visibleCols()`; build the group band row (colspans per contiguous group, pin+shadow on the pinned leader) and the `#hdr` column row (sort arrows ↑/↓, `ttl` tooltips, title fns). Header click sets `SORT` (a whitelist of keys sorts ascending first: advisor, pe, company, stage, renewal, seldl, subdl, funding, lastupd, altreqd, closedon, bostatus, carrier, outcome; others descending), resets PAGE=1. Sort the FULL `filtered()` set via `col.s` with null-last + company tiebreak. **Pagination = filter→sort→slice**: `pages=ceil(total/PAGE_SIZE)`, clamp PAGE, `shown=data.slice(start,end)`; only the current page's rows enter the DOM; the open drill row appends `detailRow`. Footer = rows-per-page select (50/100/250), Prev/Next, page jump input "Page X of Y", and "Showing a–b of N (filtered from M)". `syncTopScroll()` mirrors the top scrollbar width to the table; `updateCohortPill()` and `updateTabCounts()` refresh the header pill and tab counts.

## 11. Drill-down (`detailRow`)

Row click toggles `OPEN`; the expanded `<tr class="detail">` renders sections in this order: **Overall case summary** (de-identified `case_summary` + cross-type open-cases chips) → **Renewal-cycle timeline** (`drillTimeline`: Cycle open → Default built → Rec sent → Alt requested → Alt published → Selection → Renewal, done/pending dots, won/lost end styling) → **General** (`genPairs`; Closed unshift Outcome + Closed on) → **Customer Contact** (`contactPairs`: intro/connect, last email out/in with "Nd ago", last SF update, email awaiting reply) → **Survey answers** → **Premium & lines** (`premPairs` incl. Premium Δ (medical) and MRR before→after→Δ; then `drillEnrollment` table = Line · Carrier b→a · Enrolled b→a · Δ Enrolled · Packet with totals row; then `drillPremium` table = Line · Expiring · Default(offered menu) · Selected(offered menu) · Premium Δ, medical first, HSA/FSA/DCA carry no premium) → **Flags** (`flagPairs` incl. LF+savings+recommended-in-alt, recert, SEP, auto-renewal, default-automation with eligible/rate-parse dots, BoR, blocked reason, RFD/ERC/ALT SLA) → **Recommendation** (`recPairs`) → **Sentiment** (`surveys_12mo` mini-table newest-first) → **Benefit order** (`boPairs` + tickets_list table linking to `gusto.my.salesforce.com/<id>`). A highlighted **risk "why"** line sits at the top: Open groups firing signals into 4 clusters (Customer connection = nointro/silence/noresp; Minimal SF update = stagnant; Recommendation = rate/altsla/lfpend; Flags = termbor/sepgr/recert/packet/deadline/subdl/unworked/lategen); PF/Closed render a flat "Driven by …" (Closed prefixed "Archived — "). Header has a "Customer Positioning →" button (`data-script=opp_id15`) and Opportunity/Hippo/BO links.

**Premium basis by phase**: Open/PF headline Δ = `rate_increase_pct` ("Projected"); Closed = medical line `d_fin` ("Final"). `drillPremium` expiring field = `pr_exp_n` (closed, enrolled) vs `pr_exp_e` (open/PF, eligible); Default=`pr_dflt`, Selected=`pr_sel` (menu averages).

## 12. Customer Positioning talk track (`buildScript`)

`TIER_NAMES` = P1..P5 labels. `F(v)` = filled indigo `<strong class="fill">`, `PH(v)` = `<em>[placeholder]</em>`. `scriptVars(r)` derives advisor/renewal/carrier/rate-range (±1/2 if `rate_status==="computed"` else ±3/4)/deadlines. `buildScript(r)` toggles conditional modules on `on={high:inc>=15, sep, recert, lf, k401:!r, packet:/Renewal Packet/, term:bor_term}`, renders a "Before you dial" prep table (when live), a flow bar (struck-through = dropped), 7 numbered beats (value statement, upfront contract, discovery, cost preview, timeline, LF tease/skip, close) with conditional blocks (above-market, SEP, recert, packet, retirement, term heads-up), an objection-handling section (filtered by `on`), voicemail scripts, and a Do/Don't hygiene grid. `.doc.sampleonly` (toggle `#tSample`) hides everything but the sample lines. `buildScriptSearch()` builds a datalist over all companies (duplicate names disambiguated by PE/advisor+opp id). Footer states no customer PII is surfaced (names/phones are placeholders by design).

## 13. Overview tab

State: `OVSCOPE={mode:"team",peSel,icSel}`, `OVSTAGE` (null|open|pf|closed stage-tile filter), `OVRISK={open,pf}` (expanded risk tier per box). `OV_HI="#c0392b"`, `OV_MED="#e0a83e"`, `OV_LO="#5aa87f"`. `ovScopeBar()` = IC/PE/Team-wide chips + a PE/IC multi-select when in that mode. `ovStageCards(g)` = 3 clickable tiles (Open/PF live: opps, MRR before, at-risk High count/%/$; Closed: opps, MRR before→after, "risk archived"); click toggles `OVSTAGE`. `ovInsights(L,O)` = "Book insights" 5-column strip: **OUTREACH** (intro complete %, connect rate, email due, outreach pending no-rec), **AGING** (median + #>14d for last contact/outbound/inbound/SF update), **RECOMMENDATION & SLA** (default rec sent %, days-to-default, time in RFD, time in ERC, RFD/ERC/ALT SLA missed counts, alt published %, avg alt packages, days-to-alt), **PREMIUM (medical)** (median Δ, **≥15%**, **≥20%**), **FLAGS** (LF available %, auto-renewal %, default automation %, recert open, packet needed, BoR/Term). `ovRiskOpenTiers(O)` = P1–P5 bars (total scaled to max; red overlay = High), each click-through to that tier at High risk. `ovRiskTierBox(rows,title,boxKey,LABELMAP)` = High/Med/Low bars with an expandable "what's driving it" factor panel (`OV_OPEN_FACTOR_LABEL` / `OV_PF_FACTOR_LABEL`). `ovRollup()` = PE-team table (Team mode) or IC table (PE mode): LIVE OPPS / OPEN HIGH / PF HIGH / AT-RISK TOTAL, click a PE→its roll-up, an IC→its book. `ovDrill()` applies the current scope + tier/risk to the grid `SEL`s and calls `showTab(tab)`. Delegated click handler on `#ovBody` routes `data-ovstage` / `data-ovrisktier` / `.ov-seg` / `data-ovtier` / `data-ovtab` / `data-ovpe` / `data-ovic`.

## 14. Tabs + init (`showTab`)

`showTab(name)` toggles `.tab.on` and shows exactly one pane; guide/overview/script each hide the other three and (overview/script) call their render + scroll top; the data tabs set `TAB`, `CLOSED=(name==="closed")`, reset `OPEN`/`PAGE`, and swap the default sort between `{tier,1}` and `{closedon,-1}` when entering/leaving Closed, then `render()`. Init sequence at the bottom of the script: wire tab clicks, back/generic script buttons, sample toggle, `#fSearch` input, the synced top/bottom horizontal scroll lock, and the delegated `#body` click handler (opens the positioning script on `[data-script]`, sorts the drill line tables on `table.lines th[data-sk]`). Then `buildFilters(); buildScriptSearch(); restoreState();` sync the dropdown UIs and active tab, `render()`, and finally `showTab("overview")` (Overview is the default landing tab).

## 15. Color thresholds (quick reference)

Premium Δ / rate: **≥15% gold, ≥20% orange (`t-warn`), ≥30% red (`t-bad`)** — in the grid cell, the drill headline, and the per-line premium table; Overview premium insights report **≥15%** and **≥20%** shares. Deadlines: past→`t-bad`, ≤7d→`t-warn`. Aging emails: outbound >14/>7, inbound >21/>14. Days-in-stage >21/>14. Tickets: ≥2 warn (tix), ≥1 warn/bad (open/pastSLA). Risk tiers: High ≥35, Med ≥18, Low else.
