"""Competitor discovery: Crustdata ranked company search (canonical IDs) + web search mentions.
confirmed = description matches the product category AND an independent web result mentions the company;
possible = exactly one of those; insufficient_evidence = neither. Differentiators are not inferred."""
from __future__ import annotations

import re

from .contracts import CompetitorRecord, MarketBrief
from .crustdata_client import CrustdataClient
from .evidence import EvidenceLedger
from .normalizers import normalize_company
from .scoring import _tokens, brief_terms

ISO2 = {"United Kingdom": "GB", "United States": "US", "India": "IN", "Germany": "DE", "France": "FR", "Singapore": "SG",
        "Canada": "CA", "Australia": "AU", "Netherlands": "NL", "Ireland": "IE", "Spain": "ES", "Brazil": "BR",
        "Japan": "JP", "Sweden": "SE", "Switzerland": "CH", "United Arab Emirates": "AE"}
DESC_HITS_NEEDED = 2
FIELDS = ["basic_info", "headcount"]
_ORDER = {"confirmed": 0, "possible": 1, "insufficient_evidence": 2}


def first_sentence(text: str | None, limit: int = 220) -> str | None:
    if not text or not text.strip():
        return None
    s = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    return s[:limit]


def web_mentions(name: str, domain: str | None, results: list[dict]) -> list[tuple[int, dict]]:
    """Indexed web results whose title/snippet/url mention the company by domain or whole-word name (>=4 chars)."""
    out = []
    pat = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.I) if len(name) >= 4 else None
    for i, r in enumerate(results):
        blob = " ".join(str(r.get(k) or "") for k in ("title", "snippet", "url"))
        if (domain and domain.lower() in blob.lower()) or (pat and pat.search(blob)):
            out.append((i, r))
    return out


def find_competitors(client: CrustdataClient, brief: MarketBrief, ledger: EvidenceLedger, *,
                     max_candidates: int = 10, web_queries: int = 1) -> tuple[list[CompetitorRecord], list[str]]:
    warnings: list[str] = []
    query = brief.competitor_keywords[0] if brief.competitor_keywords else brief.product_description
    r = client.company_ranked_search(query, FIELDS, max_candidates)
    if not r.ok or not isinstance(r.body, dict):
        return [], [f"competitors: ranked company search failed ({r.error_type})"]
    cands = r.body.get("companies") or []

    web_results: list[dict] = []
    web_ref = None
    for q in ([f"{query} vendors"] + [f"{k} alternatives" for k in brief.competitor_keywords[1:]])[:web_queries]:
        w = client.web_search(q, ISO2.get(brief.target_country))
        if w.ok and isinstance(w.body, dict):
            web_results.extend(x for x in (w.body.get("results") or []) if isinstance(x, dict))
            web_ref = web_ref or (w.run.raw_path, w.retrieved_at)
        else:
            warnings.append(f"competitors: web search failed ({w.error_type}); classification uses company data only")

    terms = brief_terms(brief)
    out: list[CompetitorRecord] = []
    for item in cands:
        c = normalize_company(item, ledger=ledger, source_kind="crustdata_company_search_ranked",
                              raw_ref=r.run.raw_path, retrieved_at=r.retrieved_at)
        if not c.company_id:
            continue
        hits = len(terms & _tokens(c.description or ""))
        mentions = web_mentions(c.name, c.domain, web_results)
        ev_ids = [e for e in c.evidence_ids]
        src_url = None
        if mentions:
            i, res = mentions[0]
            src_url = res.get("url")
            ev_ids.append(ledger.add(
                subject_type="competitor", subject_id=c.company_id, claim=f"Web result mentions {c.name}: {res.get('title')}",
                source_kind="crustdata_web_search", source_record_id=c.company_id, source_url=src_url,
                field_path=f"results[{i}].snippet", raw_ref=web_ref[0],
                value_observed=str(res.get("snippet") or "")[:300], status="supported",
                retrieved_at_utc=web_ref[1],  # mentions exist only when web_ref is set
                notes="mention only; does not prove product overlap").evidence_id)
        desc_ok = hits >= DESC_HITS_NEEDED
        cls = "confirmed" if desc_ok and mentions else "possible" if desc_ok or mentions else "insufficient_evidence"
        out.append(CompetitorRecord(
            company_id=c.company_id, name=c.name, domain=c.domain, classification=cls,
            positioning_claim=first_sentence(c.description), source_url=src_url or c.linkedin_url,
            employee_count=c.employee_count, headcount_growth_6m=c.headcount_growth_6m, evidence_ids=ev_ids,
            identity=c.identity))
    out.sort(key=lambda x: (_ORDER[x.classification], x.name.lower()))
    return out, warnings
