"""Bottom-up market sizing: separate observed counts from client-assumed money. No ACV => no money figures."""
from __future__ import annotations

from .contracts import CompanyRecord, MarketBrief, SizingResult


def _money(cur: str | None, v: float) -> str:
    return f"{cur or ''} {v:,.0f}".strip()


def compute_sizing(brief: MarketBrief, observed_count: int | None, shortlist: list[CompanyRecord],
                   post_filters: list[str] | None = None) -> SizingResult:
    """observed_count = provider total_count for the server-side filters (an indexed count, not the whole market).
    pipeline pool counts only shortlisted accounts with a resolved identity inside the ICP."""
    caveats = ["Observed count is Crustdata's indexed company count for these filters; it may under-cover the market.",
               "Headcount, hiring and funding are indicators, not proof of purchase intent."]
    if post_filters:
        caveats.append("Count is NOT reduced by post-filters applied client-side: " + "; ".join(post_filters))
    acv, cur = brief.annual_contract_value, brief.currency
    eligible = [c for c in shortlist if c.wave in ("Wave 1", "Wave 2", "Research Needed")
                and c.identity.method != "unresolved" and c.icp_match is not False]
    if observed_count is None:
        caveats.append("Provider returned no total_count; observed universe size is unknown.")
    if acv is None:
        caveats.append("No annual contract value supplied: monetary estimates omitted (none assumed).")
        return SizingResult(observed_count=observed_count, formula_text=(
            f"Observed eligible companies: {observed_count:,} (indexed). No ACV supplied, so no money figure is computed."
            if observed_count is not None else "Observed universe size unknown and no ACV supplied."), caveats=caveats)
    caveats.append(f"ACV of {_money(cur, acv)} is client-supplied, not validated; pool is illustrative, not TAM or forecast revenue.")
    pool = round(observed_count * acv, 2) if observed_count is not None else None
    pipeline = round(len(eligible) * acv, 2)
    lines = []
    if pool is not None:
        lines.append(f"Serviceable pool = {observed_count:,} indexed companies × {_money(cur, acv)} ACV = {_money(cur, pool)}")
    lines.append(f"Identified pipeline = {len(eligible)} shortlisted resolved accounts × {_money(cur, acv)} ACV = {_money(cur, pipeline)}")
    return SizingResult(observed_count=observed_count, acv=acv, currency=cur, pool=pool, pipeline_pool=pipeline,
                        formula_text="\n".join(lines), caveats=caveats)


def verify_sizing(s: SizingResult, shortlist_eligible: int) -> list[str]:
    """Independent recomputation used by the verifier. Returns a list of discrepancies (empty = OK)."""
    bad = []
    if s.acv is None:
        if s.pool is not None or s.pipeline_pool is not None:
            bad.append("money figure present without ACV")
        return bad
    if s.observed_count is not None and s.pool != round(s.observed_count * s.acv, 2):
        bad.append(f"pool {s.pool} != {s.observed_count} x {s.acv}")
    if s.pipeline_pool != round(shortlist_eligible * s.acv, 2):
        bad.append(f"pipeline {s.pipeline_pool} != {shortlist_eligible} x {s.acv}")
    return bad
