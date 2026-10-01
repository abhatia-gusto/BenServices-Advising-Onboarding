# lf/ — Level-Funded Conversion dashboard (SF-CLI pull)
`pipeline/prepull.py` pulls the classifier's 3 narrative channels (Notes__c, OpportunityFeed
TextPost/ContentPost, Benefits-Renewal-Case EmailMessage bodies) via the `sf` CLI and writes a
**byte-stable** `bundles.json`. The classifier itself is unchanged — Claude subagents read the
bundles from disk per `pipeline/classifier_instructions.md`. Caps/cleaning (2500/400/600,
quoted-history strip, noise drop) and the 13-code taxonomy are identical to the live pipeline.
Data JSONs (signal_enrich.json, dash_data.json, bundles) stay local — never committed.
