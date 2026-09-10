# Salesforce-MCP morning pull — Advising Hub (3 live field groups)

These 3 field groups are **not in the Snowflake SF mirror** and must be pulled **live from the
Salesforce MCP by the task orchestrator each morning, BEFORE** running `refresh_advising_hub.py`.
The python pipeline does **not** make these calls — it only reads the 3 CSVs this step writes
(`merge_freeze` → `hub_queries/catalog.json` → `salesforce_mcp`). If a CSV is missing, every group
carries forward its prior value, so a headless python-only run still succeeds.

## Opp-id source (universe)
Open/PF opps only: read `_renewal_vnext/advising_vnext_data.json`, take `opp_id18` where
`closed == false` (~7.4k opps). Closed opps are frozen — do **not** pull or write them.

## Batching
- Chunk the opp-id list and use `... IN ( '<id>', '<id>', ... )`.
- Intro (Case) & Recert (Ticket__c): **≤ 200 ids/query**.
- Packets (ContentDocumentLink): **≤ ~50 ids/query** (ContentDocumentLink requires a
  `LinkedEntityId` equals/`IN` filter and returns one row per file, so output is large).
- Use `query_more` to page any result where `done == false`.

## Output CSVs (write into `_renewal_vnext/out/`)
Company/plan grain only — flags, picklist, filenames/carriers. **No** employee names/emails/phones/note text.
- `_renewal_vnext/out/sf_mcp_intro.csv`   → `opp_id18,intro_call,intro_call_date`
- `_renewal_vnext/out/sf_mcp_recert.csv`  → `opp_id18,recert_status`
- `_renewal_vnext/out/sf_mcp_packets.csv` → `opp_id18,packets_files,packet_carriers`

---

## 1. intro_call / intro_call_date  — SF `Case`
```soql
SELECT Opportunity__c oid, MIN(CreatedDate) mind
FROM Case
WHERE RecordType.Name = 'Benefits Renewal Case'
  AND Intro_Call_Completed__c = true
  AND Opportunity__c IN ( :batch_of_up_to_200 )
GROUP BY Opportunity__c
```
- Join: `Case.Opportunity__c` = opp 18-char id.
- `Intro_Call_Completed__c` is a **Checkbox** — there is **no** dedicated intro-call date field on
  Case, so `intro_call_date` = the **CreatedDate (date part) of the completed Benefits Renewal Case**
  (`MIN` if several). This matches the original pipeline's `intro.json` semantics.
- Derive per queried opp: `intro_call = 'Y'` if the opp is returned, else `'N'`;
  `intro_call_date` = `mind`'s date (`YYYY-MM-DD`) if returned, else empty.
- **Write a row for every queried Open/PF opp** (both Y and N).

## 2. recert_status — SF `Ticket__c`
```soql
SELECT Opportunity__c, Recert_Status__c, CreatedDate
FROM Ticket__c
WHERE Recert_Status__c != null
  AND Opportunity__c IN ( :batch_of_up_to_200 )
```
- Join: `Ticket__c.Opportunity__c` = opp 18-char id.
- Recert tickets carry `RecordType.Name = 'Advising Fulfillment'`; the reliable identifier is
  `Recert_Status__c != null`.
- Derive: `recert_status` = `Recert_Status__c` of the **most recent ticket by `CreatedDate`** per opp
  (the current status). Picklist values seen: `Recert Approved`, `Recert Failed`, `Sent to carrier`,
  `Advisor action needed`, `Customer unresponsive`.
- **Write only opps that have a recert ticket** (opps with no recert ticket are omitted → carry forward).

## 3. packets_files / packet_carriers — SF `ContentDocumentLink`
```soql
SELECT LinkedEntityId, ContentDocument.Title, ContentDocument.CreatedDate
FROM ContentDocumentLink
WHERE ContentDocument.Title LIKE '%Renewal Packet%'
  AND LinkedEntityId IN ( :batch_of_up_to_50 )
```
- Join: `ContentDocumentLink.LinkedEntityId` = opp **Opportunity** 18-char id (packets link to the
  Opportunity, confirmed — not the Case).
- Derive per opp:
  - `packets_files` = raw count of matching docs.
  - `packet_carriers`: for each doc, parse the carrier from the Title = text **after the LAST
    date-token** (regex `\d{4}-?\d{1,2}-?\d{1,2}`) and **before** `Renewal Packet`; if no date token,
    use the whole text before `Renewal Packet`. Keep the **latest `CreatedDate` per carrier**, sort by
    `(latest_date, carrier)`, and join as `Carrier (YYYY-MM-DD)` with ` · ` (U+00B7).
    Do **not** canonicalize carrier names (keep raw title text, e.g. `UnitedHealthcare CO`).
- **Write only opps with ≥1 renewal-packet file.**
- Reference parser (validated 80/80 files + carrier-strings vs the prior dataset):
  `_renewal_vnext/out/_build_sfmcp_csvs.py` (`parse_carrier`).

---

## After the pull
Run: `python3 refresh_advising_hub.py --no-publish` (the orchestrator publishes at the end).
`merge_freeze` reads the 3 CSVs and sets the fields on Open/PF opps; absent opps/CSVs carry forward;
Closed stays frozen. Expect the log line: `SF-MCP live fields: intro=… recert=… packets=…`.
