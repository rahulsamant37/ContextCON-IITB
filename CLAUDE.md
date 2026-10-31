# MarketEntryOS — ContextCon IIT Bombay (5h sprint, freeze 3:30 PM IST)
Specs: docs/MarketEntryOS_Hackathon_Spec.md, docs/ContextCon PS - CrustData.md

## Non-negotiables
- LLM = parsing + prose + planning ONLY. Facts, filters, scores, arithmetic, CRM writes = Python.
- NEVER invent company/person/financial facts. Missing => null/"unknown" + visible flag.
- NEVER guess Crustdata filter/field names. Derive from live responses saved in fixtures/raw/.
- Every claim => Evidence record (source, field_path, retrieved_at, status).
- No contact with real people. Outreach = unsent drafts in SQLite only.
- API key from env CRUSTDATA_API_KEY only; never in repo/logs/evidence.
- Headers: Authorization: Bearer, x-api-version: 2025-11-01.
- Cost caps via config; cache per mission; log every call in tool_runs.
- Idempotent re-runs (no duplicate CRM rows). Bounded retries + backoff; partial results preserved.
- Scope discipline: ONE orchestrator + python functions. No multi-agent chatter.

## Stack
Python 3.11, pydantic, httpx, FastAPI (optional), SQLite, Streamlit, pytest, jinja2 (HTML report -> PDF fallback).

## Workflow
Small commits per milestone. Run pytest before commit. Keep fixtures for offline replay mode (REPLAY=1).