# MarketEntryOS — Autonomous Market-Entry Consulting Firm

**Product and technical specification | ContextCon IIT Bombay 2026–27**  
**Status:** Hackathon implementation blueprint  
**Build window:** October 31, 2026, 10:30 AM–3:30 PM IST  
**Primary data infrastructure:** Crustdata company/person identity graph and search/enrichment APIs

## 1. One-line pitch

**Give MarketEntryOS a product, a target geography, and a customer profile. It autonomously researches the market, sizes the addressable account universe, identifies competitors and buyers, prioritizes target companies, and delivers a verified market-entry engagement with a functioning local CRM—without manual research or follow-up prompts.**

## 2. The professional service being replaced

MarketEntryOS replaces a *bounded B2B market-entry research and go-to-market preparation engagement* traditionally staffed by market researchers, strategy consultants, competitive analysts, prospect researchers, and sales-operations specialists.

**Work completed:** customer segmentation; searchable company-market mapping; bottom-up market sizing with explicit assumptions; competitor landscape; verified buyer mapping; account qualification; launch sequencing; CRM population; exportable client reports and evidence dossier.

**Not claimed:** registering a company abroad, obtaining legal approvals, delivering paid advertising, contacting real prospects, negotiating contracts, or closing deals. No external person may be contacted during this hackathon; execute only against permitted APIs and local/sandbox systems.

### Target user

A B2B SaaS founder, head of growth, or strategy manager assessing entry into a new industry/geographic market.

### Business outcome

A complete, auditable launch-ready *research and sales-operations packet*, not a conversational answer or a handful of suggested accounts.

## 3. Example request (the demo input)

> We sell cybersecurity compliance software for financial technology companies. Evaluate entry into the UK fintech market. Focus on companies with 50–500 employees. Estimate the addressable company universe using a £12,000 annual contract value assumption; identify competitors and buyer roles; produce a ranked target-account shortlist; create a staged CRM campaign and an evidence-backed market-entry recommendation.

The system must also handle an **unseen prompt** using another supported sector, geography, and employee range without hand-edited results.

### Required input object

```json
{
  "product_name": "ComplianceCloud",
  "product_description": "B2B cybersecurity compliance workflow software",
  "target_country": "United Kingdom",
  "target_industry": "Financial technology",
  "employee_min": 50,
  "employee_max": 500,
  "annual_contract_value": 12000,
  "currency": "GBP",
  "target_buyer_roles": ["Head of Compliance", "CISO", "VP Security"],
  "max_target_accounts": 20,
  "max_company_enrichments": 10,
  "max_contacts_per_company": 2,
  "competitor_keywords": ["compliance automation", "security compliance"]
}
```

The natural-language parser creates this schema. If key assumptions such as annual contract value are missing, the agent records the omission and omits monetary estimates (or uses an explicitly labeled, user-supplied assumption); it must **not invent financial figures**.

## 4. Definition of done: five downloadable deliverables and one operational state

1. **`Market_Entry_Report.pdf`** — executive recommendation; segmentation; competitor overview; bottom-up market sizing; assumptions; key risks; prioritized launch plan.
2. **`Target_Accounts.csv`** — resolved company name, Crustdata company ID, domain, country, industry, size, growth/hiring indicators (where present), fit score, verification status, and evidence references.
3. **`Buyer_Map.csv`** — each verified person's identity, role, current employer, company ID/domain linkage, source references, and missing-data flags; no speculative email addresses.
4. **`Competitive_Landscape.csv`** — relevant competitors, their publicly supported positioning claims, differentiators, and evidence links.
5. **`Evidence_Log.json`** — every claim's provenance, field path, retrieved timestamp, verification status, and contradictions.
6. **Populated local CRM (`marketentry.db`)** — companies, contacts, segments, stage, tasks, and unsent outreach drafts. Show real rows inserted by the agent. No communication with external people.

If full PDF rendering threatens the deadline, an HTML report that can print to PDF is an acceptable hackathon fallback; the evidence and CRM are higher priority than PDF cosmetics.

## 5. End-to-end autonomous workflow

### Step A — Brief interpretation

- Parse natural-language mission into validated `MarketBrief`.
- Resolve geography, industry, company-size and buyer-role constraints.
- Produce an explicit assumption ledger and task plan.
- Validate available Crustdata filter fields against the walkthrough/docs before issuing requests. Unsupported constraints become **post-filter rules** or a disclosed limitation; never silently ignore them.

### Step B — Company-universe discovery

- Query **Company Search** for relevant companies within supported filter boundaries.
- Read `total_count` and paginate only within the configured result/credit cap.
- Record query filters, returned count, date and any coverage limitations.
- Resolve/de-duplicate the companies by Crustdata canonical company ID, fallback domain, then verified name.
- Use **Company Identify** where a name/domain needs resolution.

**Output:** auditable candidate-account universe and segment counts. The search result count is an *observed indexed count*, not guaranteed to equal all businesses in that market.

### Step C — Target-account enrichment and ranking

- Enrich the top eligible candidate companies using **Company Enrich**.
- Extract available firmographic, headcount, funding, hiring and technographic fields.
- Prefer company ID/domain matches; reject ambiguous records that cannot be confidently linked.
- Apply an explicit, deterministic scoring rubric.

**Example rubric (100-point maximum):** ICP match 35, growth signals 20, relevant hiring signals 15, product-need fit 15, buyer-map availability 15. Use only observed evidence. Show `unknown` rather than silently treating missing evidence as a negative. Display coverage/confidence separately from the score.

### Step D — Competitor research

- Discover candidate competitors through keyword/company queries and Crustdata Web Search.
- Identity-resolve each relevant company, enrich selected competitors, and fetch supporting source pages only as needed.
- Compare supported positioning, size/growth signals, technology or product overlap where evidence exists.
- Distinguish **confirmed competitor**, **possible competitor**, and **insufficient evidence**.

### Step E — Buyer mapping

- For highest-ranked accounts, use **Person Search** to discover professionals in target buyer roles.
- Verify current employer against the account's Crustdata ID/domain and available employment history.
- Enrich at most the configured number of people when essential.
- If no trustworthy contacts exist, mark the account `buyer_not_found`; do not fabricate names, titles, addresses or emails.

### Step F — Market sizing and entry recommendation

Calculate separate concepts instead of inventing one giant TAM figure:

- **Observed eligible company count:** Crustdata search count meeting the scoped filters, qualified as coverage-limited.
- **Illustrative serviceable annual contract value pool:** observed eligible count × **client-provided ACV**, with currency explicitly stated.
- **Identified obtainable pipeline pool:** sum of client-provided ACV assumptions across the verified shortlist; **not** forecast revenue.
- **First-wave launch prioritization:** derived from fit, observable buying signals, buyer coverage and uncertainty.

Record exact search filters, arithmetic inputs, and assumptions in the report. Never present company headcount, hiring activity or contact count as proof of purchase intent.

### Step G — Verification and correction loop

For every client-facing material claim, create a structured evidence record. The verifier:

1. Checks whether a source record actually contains the claimed fact.
2. Confirms that the source belongs to the correct canonical company/person identity.
3. Checks age/retrieval time and flags stale data or material conflicts.
4. Recomputes all numeric outputs deterministically.
5. Rejects or qualifies claims that lack support.
6. Makes a limited retry or falls back to `unverified`/`unknown` when a tool fails.

**Rule:** The LLM writes prose and planning; source records and Python determine factual claims, filtering, arithmetic, scores, and CRM updates.

### Step H — Execute the consulting deliverable

- Save ranked companies and verified contacts to SQLite.
- Create local campaign segments: `Wave 1`, `Wave 2`, and `Research Needed`.
- Generate tailored *drafts only* for each account, tied to evidence, without sending.
- Generate a launch checklist and research-completion report.
- Export reports, CSVs, and JSON evidence.
- Return a single `MissionResult` with artifact paths, execution state, warnings and verification stats.

## 6. Crustdata implementation contract

**Base URL:** `https://api.crustdata.com`  
**Headers:** `Authorization: Bearer $CRUSTDATA_API_KEY`, `x-api-version: 2025-11-01`, `Content-Type: application/json`.

| Integration | Verified API path | MVP role |
|---|---|---|
| Company Search | `POST /company/search` | Find/filter company universe and retrieve count |
| Company Identify | `POST /company/identify` | Resolve supplied names/domains to canonical company records |
| Company Enrich | `POST /company/enrich` | Retrieve available headcount, funding, hiring and firmographics |
| Person Search | `POST /person/search` | Identify relevant buyer roles and professional histories |
| Person Enrich | `POST /person/enrich` | Deepen selected, confidently matched people records |
| Web Search | `POST /web/search/live` | Source-backed competitor/context discovery |
| Web Fetch | `POST /web/enrich/live` | Fetch selected source pages for verification |

**Important:** The exact company geography/industry filter names and person employer matching fields must be validated against the live schema/API walkthrough. The adapter maps the provider's response to internal stable objects; the UI and agents must not depend on undocumented provider fields.

**Cost controls:** Configurable `max_company_search_results`, `max_company_enrichments`, `max_person_results`, `max_person_enrichments`, and `max_web_queries`. Cache responses per mission and only enrich after identity resolution; track actual API responses and credit use. Never claim real-time monitoring if the MVP only performs a one-off search.

Provider documentation: https://crustdata.com/company-data-api , https://crustdata.com/people-api , https://crustdata.com/mcp-server , https://crustdata.com/blog/replace-clay-workflow-claude-api

## 7. Agent architecture

```text
User brief
    |
    v
Brief Parser / Mission Controller
    |
    +--> Market Mapper ------> Company Search / Identify
    |
    +--> Account Analyst ----> Company Enrich
    |
    +--> Competitor Analyst -> Company Search + Web Search/Fetch
    |
    +--> Buyer Mapper -------> Person Search / Enrich
    |
    v
Deterministic Strategy + Market-Sizing Engine
    |
    v
Evidence Verifier (check IDs, sources, numbers, contradictions)
    |
    v
Execution Layer (SQLite CRM + file exporters + unsent drafts)
    |
    v
Report + evidence dossier + run log
```

**Recommended implementation:** One orchestrator with specialized Python functions and a verifier; multiple concurrently chatting LLM agents are not necessary. Treat task state as an explicit workflow with step status, retry count, cached API results and final artifacts. The mission must progress automatically from request to completion with no intermediate user confirmations.

## 8. Internal data contracts

### `CompanyRecord`

```json
{
  "company_id": "provider-company-id",
  "name": "Example Company",
  "domain": "example.com",
  "country": "United Kingdom",
  "industry": "Fintech",
  "employee_count": null,
  "headcount_growth_6m": null,
  "open_roles": null,
  "icp_match": true,
  "fit_score": null,
  "data_coverage": 0.0,
  "evidence_ids": [],
  "verification_status": "unverified"
}
```

### `Evidence`

```json
{
  "evidence_id": "ev_0001",
  "subject_type": "company",
  "subject_id": "provider-company-id",
  "claim": "Company employs approximately 200 people",
  "source_kind": "crustdata_company_enrich",
  "source_record_id": "provider-company-id",
  "source_url": null,
  "field_path": "headcount.total",
  "retrieved_at_utc": "ISO-8601 timestamp",
  "status": "supported",
  "notes": "Provider-reported estimate"
}
```

Evidence must be traceable to the saved API response or actual web URL. When a field is absent, store `null`; sample data above are schema illustrations, not claims about any real business.

### `MissionResult`

```json
{
  "mission_id": "mission_001",
  "state": "completed_with_warnings",
  "company_records": 20,
  "buyer_records": 0,
  "verified_claim_fraction": null,
  "artifacts": ["Market_Entry_Report.pdf", "Target_Accounts.csv", "Evidence_Log.json"],
  "warnings": ["Buyer-search data unavailable for some companies"]
}
```

## 9. Storage and APIs for the app

**SQLite tables:**

- `missions(id, raw_prompt, normalized_brief_json, status, started_at, finished_at, warnings_json)`
- `companies(id, mission_id, crustdata_company_id, domain, normalized_json, fit_score, coverage_score, verification_status)`
- `people(id, mission_id, crustdata_person_id, company_id, normalized_json, verified_employment)`
- `evidence(id, mission_id, subject_id, claim, source_type, source_pointer, field_path, retrieved_at, status)`
- `tool_runs(id, mission_id, tool_name, request_hash, result_status, duration_ms, credit_cost, error_type)`
- `crm_tasks(id, mission_id, company_id, task_type, title, status, draft_text)`

**Recommended FastAPI endpoints:**

- `POST /missions` — create mission from free-text request plus optional structured settings.
- `GET /missions/{id}` — status, completed steps and warnings.
- `GET /missions/{id}/accounts` — ranked accounts with evidence links.
- `GET /missions/{id}/evidence` — audit log and verification summaries.
- `GET /missions/{id}/artifacts/{name}` — export artifact.

**UI:** Streamlit is adequate for a five-hour build. Four panes are sufficient: Request, Live Execution Trace, Market Intelligence, and Deliverables/CRM.

## 10. Non-functional requirements and failure behavior

- **Autonomy:** One initial request; the agent runs to deliverables without user interaction.
- **Canonical identity:** Every mapped account has an ID/domain provenance and a documented match decision.
- **No unsupported claims:** Missing values become `unknown`, not fabricated company facts or financial numbers.
- **Tool resilience:** Bounded retries and exponential backoff for rate limits/transient errors; parse error responses safely; preserve partial valid results.
- **Idempotence:** Re-running a mission must not insert duplicate CRM accounts or contacts.
- **Privacy and rules:** No unsolicited communication, real purchases, external outreach or interaction with real people; no sensitive personal details beyond required work-profile fields.
- **Security:** API credentials from environment variables only; never store them in the repository or export them in evidence logs.
- **Observability:** Show actual API calls, normalized records, failed steps and warnings; do not disguise pre-generated content as live results.

## 11. Five-hour MVP versus later product

| Required by code freeze | Stretch / post-hackathon |
|---|---|
| Natural-language mission parser with stable brief schema | Complex multilingual requirements |
| Crustdata company discovery and ID resolution | Continuous country-by-country monitoring |
| Top 10 account enrichment | Thousands of enriched accounts |
| Deterministic scoring and market-sizing assumptions | Calibrated predictive conversion models |
| Buyer mapping for top 5 accounts | Complete multi-threaded buying committees |
| Competitor shortlist with sources | Full pricing and product benchmarking |
| Evidence log with verification and unknowns | Cryptographically signed provenance |
| Live UI, actual SQLite writes, CSV + HTML/PDF | HubSpot/Salesforce production write-back |
| Two-minute recorded end-to-end demonstration | Real-world rollout and paid campaigns |

**Priority order if time is short:** functioning Crustdata company search → normalized records → market sizing → CRM write → evidence verifier → buyer mapping → competitor research → visual polish.

## 12. Execution schedule: October 31, 2026

| Time (IST) | Deliverable |
|---|---|
| 10:30–11:10 | Repository, API authentication, first live company search, saved raw response |
| 11:10–12:00 | Mission input parser, company ID resolution, normalized records |
| 12:00–12:45 | Enrichment, filters, ranking, observed-market calculations |
| 12:45–1:30 | Buyer search and small competitor research workflow |
| 1:30–2:10 | Evidence graph/verification and SQLite CRM writes |
| 2:10–2:45 | Streamlit dashboard + CSV/HTML report exports |
| 2:45–3:05 | Run an unseen request; test failure/empty-data cases |
| 3:05–3:30 | Record two-minute screen demo; final checks; submit repository/video |

**Critical scheduling rule:** The problem statement permits design and architecture preparation before 10:30 AM, but actual coding begins only then. Code freeze/submission is 3:30 PM.

## 13. Acceptance tests (the judges should be able to observe these)

1. A new sector/geography prompt starts and finishes one mission without any additional prompts.
2. At least one genuine Crustdata Company Search and Company Enrich response is visible in trace/evidence; buyer/search runs execute where data are available.
3. Every exported account is de-duplicated, traceable to canonical identity or clearly marked unresolved.
4. The market-size calculation displays observed company count, the client-supplied ACV and the resulting multiplication; it is labeled as an indexed, assumption-based estimate.
5. No company/person fact appears in the final report without evidence or a visible uncertainty flag.
6. Empty results, ambiguous identity and one simulated transient API failure produce honest warnings—not fabricated replacements or a crash.
7. The local CRM visibly contains new accounts, wave assignments and research/outreach draft tasks.
8. Final report, account CSV and evidence JSON are saved as actual downloadable files.
9. No message is sent to a real person; outreach content stays in an unsent local draft.
10. The demo video includes the new input, visible tool execution, final research packet, audit drill-down and actual CRM state.

## 14. The two-minute demo storyboard

- **0:00–0:15:** The client gives an unfamiliar market-entry request and presses Run.
- **0:15–0:35:** Show genuine Crustdata tool calls, company-universe count and identity resolution.
- **0:35–0:55:** Show ranked accounts, company attributes and buyer matching.
- **0:55–1:15:** Open bottom-up market-sizing formulas, competitor landscape and assumptions.
- **1:15–1:40:** Drill into one claim; show raw evidence, timestamp and verification decision; highlight one honest unknown.
- **1:40–2:00:** Open generated report/CSV and the newly populated local CRM, including staged tasks and unsent drafts.

If the full live run exceeds two minutes, record the actual run and edit it down without implying that prefilled results were generated by the displayed request.

## 15. Competitive differentiation

**Not:** “ChatGPT makes a marketing strategy” or “Crustdata finds leads.”  
**Yes:** “A single autonomous execution graph completes the evidence-heavy research, market sizing, buyer mapping, competitive analysis and CRM implementation that a market-entry consultancy normally delivers.”

The core differentiator is the **source-to-action audit chain**: every actionable CRM account and strategic recommendation links back to a canonical company/person identity, an underlying source, a calculated decision, and a completed execution record.

## 16. Risks / honest limitations

- Crustdata is company/person intelligence infrastructure, not a comprehensive authoritative registry of every business or legal filing; observed counts may under-cover the market.
- Market sizing from observed companies × assumed ACV is an illustrative serviceable-revenue proxy, not validated TAM, guaranteed spend or forecast bookings.
- Headcount, hiring and funding are indicators, not proof of demand or a precise purchase-intent score.
- Buyer mapping can be incomplete, and published professional data can be stale; no match must remain no match.
- Competitor product differentiation requires actual supporting public sources. Missing product pricing must not be invented.
- The build replaces a clearly defined research-and-operations engagement, not every legal, human sales, and operational function of international expansion.

## 17. Judging alignment

| ContextCon criterion | MarketEntryOS demonstration |
|---|---|
| End-to-end execution | One brief creates report, verified account map, buyer map, and live CRM records |
| Data integrity / verification | Crustdata canonical IDs, source-level evidence, arithmetic checks, uncertainty markers |
| Robustness and edge cases | Bounded retries, ambiguous identity handling, missing data, partial completion |
| Demo clarity | Input → live research/verification → files + actual SQLite CRM update in under two-minute walkthrough |

**Ship the smallest scope that genuinely executes from an unseen brief. A complete 10-account consultancy deliverable is stronger than a half-working, 10-agent platform.**
