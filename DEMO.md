# 2-minute demo script (spec §14)

**Pre-flight:** `scripts/dev.sh`, open http://localhost:3000 (landing page) and click **Start researching**; no sign-in. *Settings* should show both connections as connected.
A live run takes about 1 minute and about 80 credits. Record the real run and speed up the wait in the edit, and say so (spec §14).
Safety net: keep **Demo mode** ticked (the Germany example turns it on) to replay the recorded run for 0 credits.

**Request** (on *New research*, choose the *Fleet software · Germany logistics* example, not the spec's UK example):
> We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, 100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO.

| Time | Do | Say / point at |
|---|---|---|
| 0:00–0:15 | Landing page → **Start researching** → pick the example, open *Options*, untick *Demo mode*, tick *Simulate a temporary outage*, **Start research**. | "One request, no further input. Facts come from Crustdata; the AI only parses text and polishes wording." |
| 0:15–0:35 | **Progress** page: steps, live counters, open *Technical details* for the calls table. | Real `company_search` with indexed total 413, enrich, person search, credits per call; the red simulated failure then the successful retry. |
| 0:35–0:55 | Auto-opens **Results** → *Companies* tab; click a "Contact first" company. | "Why it's a match": scored only on what was found, "No data" is never a penalty; decision-makers confirmed by Crustdata company ID; "None found" proves nothing is invented. |
| 0:55–1:15 | *Overview* tab: recommendation, key numbers, priority breakdown, "Things to keep in mind"; then *Competitors* and *Brief*. | "413 companies × €9,000 = €3.7M: companies found × your contract value, a rough guide, not a forecast." Direct vs possible competitors. |
| 1:15–1:40 | Company panel → *Sources* → open "Headcount". Or the *Sources* tab search. | Value we used vs value in the saved source (green check), field path, retrieved time, "Confirmed". Point at an honest "Not available" (open jobs). |
| 1:40–2:00 | *Downloads*: get the PDF; **Open pipeline**; drag a company to *Contacted*; open it and edit its draft. | Real local CRM rows, waves, tasks, outreach drafts marked UNSENT with no send button. Re-running never duplicates rows or overwrites edits. |

**If something fails live:** the failure is the demo: warnings are honest and partial results are kept. Do not hand-edit results.
