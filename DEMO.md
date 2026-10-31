# 2-minute demo script (spec §14)

**Pre-flight:** `scripts/dev.sh`, open http://localhost:3000. *Settings* should show Crustdata API and Language model as connected.
A live run takes about 1 minute and about 80 credits. Record the real run and speed up the wait in the edit, and say so (spec §14).
Safety net: tick **Offline replay** under *Run options* (and untick *Use AI for wording*) to replay the recorded Germany run for 0 credits.

**Request** (click the *Germany logistics* example chip, not the spec's UK example):
> We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, 100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO.

| Time | Do | Say / point at |
|---|---|---|
| 0:00–0:15 | **New mission**: paste or pick the request, *Review understanding first* (optional), open *Run options*, tick *Simulate one API failure*, **Run mission**. | "One request, no further input. Facts come from Crustdata; the AI only parses text and polishes wording." |
| 0:15–0:35 | **Live run** page: stepper, activity feed, *Crustdata calls* table. | Real `company_search` with indexed total 413, enrich, person search, credits per call; the red simulated failure then the successful retry. |
| 0:35–0:55 | Auto-opens **Results** → *Accounts* tab; click a Wave 1 account. | Fit vs coverage shown separately; hatched bars = unknown, not zero; buyers verified by Crustdata company ID; a "buyer not found" row proves nothing is invented. |
| 0:55–1:15 | *Overview* tab: sizing card, launch segments, risks; *Competitors* and *Assumptions* tabs. | "413 indexed companies × €9,000 = €3,717,000: observed count × your ACV, illustrative, not TAM." Confirmed vs possible competitors. |
| 1:15–1:40 | Account drawer → *Evidence* → open "Headcount (total)". Or the *Evidence* tab search. | Field path, retrieved-at, claimed value vs the value found in the saved source (green check), status `supported`. Point at an honest **unknown** (open roles). |
| 1:40–2:00 | *Exports & CRM*: download the PDF; open **CRM board**; drag an account to *Contacted*; edit a draft. | Real local CRM rows, waves, tasks, outreach drafts marked UNSENT with no send button. Re-running never duplicates rows or overwrites edits. |

**If something fails live:** the failure is the demo: warnings are honest and partial results are kept. Do not hand-edit results.
