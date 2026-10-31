"""Deterministic account scoring. Rubric (100): ICP 35, growth 20, hiring 15, product-need 15, buyer 15.
A component with no observed evidence is None ("unknown"), never 0. fit_score is earned points over the
points that COULD be assessed; data_coverage (share of the 100 points assessable) is reported separately."""
from __future__ import annotations

import re

from .contracts import CompanyRecord, MarketBrief
from .normalizers import country_matches

WEIGHTS = {"icp_country": 10, "icp_headcount": 15, "icp_sector": 10, "growth": 20, "hiring": 15, "need": 15, "buyer": 15}
assert sum(WEIGHTS.values()) == 100
WAVE1_MIN_FIT, WAVE2_MIN_FIT, MIN_COVERAGE = 60.0, 40.0, 0.4
GROWTH_FULL_6M, GROWTH_FULL_12M = 20.0, 35.0  # % growth that earns full points
HIRING_FULL_RATIO, HIRING_FULL_ABS = 0.10, 10  # open roles / headcount, or absolute when headcount unknown
NEED_FULL_HITS = 3
_STOP = {"software", "platform", "solution", "solutions", "service", "services", "tool", "tools", "based", "that",
         "with", "from", "this", "your", "their", "companies", "company", "business", "using", "built", "workflow"}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]{3,}", text.lower()) if w not in _STOP}


def brief_terms(brief: MarketBrief) -> set[str]:
    return _tokens(" ".join([brief.product_description, *brief.competitor_keywords]))


def score_company(rec: CompanyRecord, brief: MarketBrief, *, sector_matched_by_filter: bool = True) -> CompanyRecord:
    """Return a scored copy. Never mutates the input."""
    r = rec.model_copy(deep=True)
    pts: dict[str, float | None] = {}
    reasons: list[str] = []
    icp_ok: list[bool] = []

    c = country_matches(brief.target_country, r.country)
    pts["icp_country"] = None if c is None else (WEIGHTS["icp_country"] if c else 0.0)
    if c is not None:
        icp_ok.append(c)
        reasons.append(f"country {r.country} {'matches' if c else 'does not match'} {brief.target_country}")

    hc = r.employee_count
    if hc is None:
        pts["icp_headcount"] = None
    else:
        inside = (brief.employee_min is None or hc >= brief.employee_min) and (brief.employee_max is None or hc <= brief.employee_max)
        pts["icp_headcount"] = float(WEIGHTS["icp_headcount"]) if inside else 0.0
        icp_ok.append(inside)
        reasons.append(f"headcount {hc} {'inside' if inside else 'outside'} {brief.employee_min}-{brief.employee_max}")

    pts["icp_sector"] = float(WEIGHTS["icp_sector"]) if sector_matched_by_filter else None
    if sector_matched_by_filter:
        reasons.append(f"sector matched by search filter ({brief.target_industry})")

    g, scale = (r.headcount_growth_6m, GROWTH_FULL_6M) if r.headcount_growth_6m is not None else (r.headcount_growth_12m, GROWTH_FULL_12M)
    pts["growth"] = None if g is None else round(WEIGHTS["growth"] * min(1.0, max(0.0, g / scale)), 2)

    if r.open_roles is None:
        pts["hiring"] = None
    else:
        ratio_full = (r.open_roles / r.employee_count) / HIRING_FULL_RATIO if r.employee_count else r.open_roles / HIRING_FULL_ABS
        pts["hiring"] = round(WEIGHTS["hiring"] * min(1.0, ratio_full), 2)

    terms = brief_terms(brief)
    if not r.description or not terms:
        pts["need"] = None
    else:
        hits = len(terms & _tokens(r.description))
        pts["need"] = round(WEIGHTS["need"] * min(1.0, hits / NEED_FULL_HITS), 2)
        reasons.append(f"{hits} product/category terms found in company description")

    pts["buyer"] = {"found": float(WEIGHTS["buyer"]), "buyer_not_found": 0.0}.get(r.buyer_status)

    known_max = sum(WEIGHTS[k] for k, v in pts.items() if v is not None)
    earned = sum(v for v in pts.values() if v is not None)
    r.score_breakdown = pts
    r.data_coverage = round(known_max / 100, 3)
    r.fit_score = round(100 * earned / known_max, 1) if known_max else None
    r.confidence = "high" if r.data_coverage >= 0.8 else "medium" if r.data_coverage >= 0.5 else "low"
    r.icp_match = None if not icp_ok else all(icp_ok)
    r.icp_reasons = reasons
    r.flags = [f for f in r.flags if not f.startswith("unknown:")] + [f"unknown:{k}" for k, v in pts.items() if v is None]
    return r


def assign_wave(r: CompanyRecord) -> str | None:
    """None = outside the ICP (not shortlisted)."""
    if r.icp_match is False:
        return None
    if r.identity.method == "unresolved" or r.data_coverage < MIN_COVERAGE or r.fit_score is None:
        return "Research Needed"
    if r.fit_score >= WAVE1_MIN_FIT and r.buyer_status == "found" and r.confidence != "low":
        return "Wave 1"
    if r.fit_score >= WAVE2_MIN_FIT:
        return "Wave 2"
    return "Research Needed"


def rank_companies(recs: list[CompanyRecord]) -> list[CompanyRecord]:
    return sorted(recs, key=lambda r: (-(r.fit_score if r.fit_score is not None else -1), -r.data_coverage, r.name.lower()))


def score_and_rank(recs: list[CompanyRecord], brief: MarketBrief, **kw) -> list[CompanyRecord]:
    out = []
    for r in recs:
        s = score_company(r, brief, **kw)
        s.wave = assign_wave(s)
        out.append(s)
    return rank_companies(out)
