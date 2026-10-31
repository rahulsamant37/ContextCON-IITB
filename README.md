# MarketEntryOS

An autonomous market-entry research and go-to-market-prep engagement, built on Crustdata's company/person graph
(ContextCon IIT Bombay). Give it one free-text request; it returns a verified research packet and a populated local CRM with
no further input.

> *"We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, 100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO."*

## What it does (one orchestrator, plain Python functions)

| Step | Module | Crustdata calls |
|---|---|---|
| A Brief | `brief_parser` (rules always; free LLM fills text fields only) | – |
| B Discovery | `orchestrator` + `normalizers` | autocomplete (free), Company Search (count + relevance-ranked pool) |
| C Enrichment | `orchestrator` | Company Enrich (top N, by canonical ID) |
| E Buyers | `buyers` | Person Search by employer domain; employer verified by Crustdata company ID |
| D Competitors | `competitors` | ranked Company Search + Web Search |
| F Sizing | `sizing` | – (observed count × client ACV) |
| G Verification | `verifier` | – (re-reads saved raw responses) |
| H Execution | `crm`, `drafts`, `exporters` | – |

Deliverables per mission in `out/<mission_id>/`: `Market_Entry_Report.pdf|html`, `Target_Accounts.csv`, `Buyer_Map.csv`,
`Competitive_Landscape.csv`, `Evidence_Log.json`; CRM in `out/marketentry.db` (companies, people, segments, tasks, evidence,
tool_runs, **unsent** outreach drafts).

## Guarantees (enforced and tested)

- **LLM = parsing + prose only.** Counts, filters, scores, arithmetic and CRM writes are Python. Numbers (headcount range, ACV) are never LLM-extracted; LLM-polished drafts are rejected if they add numbers, links or contact details.
- **No invented facts.** Missing data is `null`/`unknown` with a visible flag; unknown score components are excluded from the score and shown as lower *coverage*, not as zero.
- **Every claim has Evidence** (source, field path, retrieved-at, status). The verifier re-opens the saved response, finds the record by canonical ID, and checks the value is really there; it also flags staleness and contradictions, and recomputes sizing and scores.
- **Identity is by ID/domain, never by name.** (Live: `names:["Bits"]` returned a university at confidence 1.0; such matches are refused.)
- **No contact with real people.** No emails are collected; outreach exists only as `draft_unsent` rows.
- **Resilience:** cached per mission, bounded retries with backoff, safe error parsing, credit and web-query caps, partial results preserved, honest warnings. `SIMULATE_TRANSIENT_FAILURE=1` demonstrates it live.
- **Idempotent:** mission id = hash of the normalised brief; re-runs upsert (manual CRM stage/task status is preserved).

## The application

A web app (`web/`, Next.js 16 + TypeScript + Tailwind) on top of a FastAPI backend (`marketentry/api.py`):

- **New mission:** describe the market in plain English, optionally review and edit what was understood (country, sector, size, ACV, buyer roles, assumption ledger) with a credit estimate, then run. No further questions.
- **Live run:** step-by-step progress, plain-language activity feed and every Crustdata call with its credit cost, streamed live (Server-Sent Events).
- **Results:** verdict, KPIs, sizing (observed count × your ACV), launch segments, fit landscape, risks and launch plan; sortable accounts with a "why this score" drawer; buyers; competitors; assumptions; a searchable evidence explorer that shows the value found in the saved source.
- **Exports:** PDF/HTML report, accounts, buyer map, competitor CSVs and the evidence log.
- **CRM board:** drag-and-drop pipeline stages, task checklist and editable outreach drafts that are never sent and survive re-runs.
- **Missions and settings:** history of every run; key status (never the keys) and cost caps.

## Run

```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e .
cp .env.example .env                 # CRUSTDATA_API_KEY, optional GROQ_API_KEY (free LLM for wording only)
(cd web && pnpm install)
scripts/dev.sh                       # API http://127.0.0.1:8000 (docs at /docs) + app http://localhost:3000
```
Open **http://localhost:3000**. Set `NEXT_PUBLIC_API_URL` if the API runs elsewhere. Keys stay on the server.

Tests:
```bash
.venv/bin/python -m pytest -q                                    # engine + API, no network
cd web && pnpm exec playwright install chromium && pnpm exec playwright test        # browser e2e in offline replay: 0 credits
LIVE=1 pnpm exec playwright test e2e/live.spec.ts                                   # one real mission (~80 credits)
```
CLI (same engine, results also appear in the app's history): `.venv/bin/python scripts/run_mission.py "<request>"`.

Offline replay: `python scripts/save_fixtures.py <mission_id>` copies a live run's raw responses into `fixtures/raw/`;
then tick **Offline replay** in the app (or `REPLAY=1`) to re-run that request with zero network and zero credits
(a missing fixture is an honest `replay_miss`, never invented data).

## Honest limitations

- Crustdata is an indexed graph, not a registry: observed counts under-cover the market. Market size = indexed count × *client-supplied* ACV; it is illustrative, not TAM or forecast revenue.
- Sector is matched by Crustdata's taxonomy tag; some tagged companies are not true targets. The `need` score uses description-keyword overlap only.
- Hiring is `unknown` when the provider tracks no postings (not the same as zero openings). Buyer coverage is incomplete by nature: no match stays no match.
- Competitor differentiators/pricing are not assessed; classification uses provider descriptions plus independent web mentions.
- Person Enrich is not used (it needs LinkedIn profile URLs that Person Search does not return).

Field names and costs are documented from live responses in `docs/crustdata_schema_notes.md`.
