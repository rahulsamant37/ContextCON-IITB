# 2-minute demo script (spec §14)

**Pre-flight (once):** `cd` to repo, `.venv/bin/streamlit run marketentry/ui/app.py`. Sidebar should read *Crustdata key: set · LLM key: set*.
Keep REPLAY **off** for the real take. Safety net: toggle REPLAY on and the LLM off (the recorded Germany run replays for 0 credits).
Each live run costs about 78 credits and takes roughly 1–2 minutes (pacing keeps us under Crustdata's 30 req/min): record the real run and speed up the wait in the edit, and say so (spec §14).

**Request** (select *Germany logistics (unseen)*, not the spec's UK example):
> We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, 100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO.

| Time | Do | Say / point at |
|---|---|---|
| 0:00–0:15 | Tab **1 Request** → *Run mission*. Optionally enable *Simulate one transient API failure*. | "One request, no further input. Facts come from Crustdata; the LLM only parses text and writes wording." |
| 0:15–0:35 | Tab **2 Live execution trace**: the stream, then *Actual Crustdata calls* table. | Real `company_search` with `total_count` 413, `company_enrich`, `person_search`, credits per call. If simulated: the 503 → retry row and the warning. |
| 0:35–0:55 | Tab **3 Market intelligence** → *Ranked target accounts*; pick a Wave 1 account; open *Buyer map*. | Fit vs coverage shown separately; identity by Crustdata company ID; a `buyer_not_found` row proves nothing is fabricated. |
| 0:55–1:15 | Scroll up: *Bottom-up market sizing*, then *Competitive landscape*, *Assumption ledger*. | "413 indexed companies × EUR 9,000 = EUR 3,717,000: observed count × client ACV, labelled illustrative, not TAM." confirmed vs possible competitors. |
| 1:15–1:40 | *Score breakdown & audit drill-down*: choose the account, open an evidence record. | JSON shows field path, retrieved-at, the value found in the saved raw response, status `supported`. Point at the honest **unknown** (hiring). |
| 1:40–2:00 | Tab **4 Deliverables & CRM**: download PDF/CSV; CRM tables; *Tasks & unsent drafts*. | Real rows, waves, `draft_unsent` outreach, nothing sent. Mention re-run creates no duplicates. |

**If something fails live:** the failure is the demo: warnings are honest (partial results are kept). Do not hand-edit results.
