"""Pure data-shaping helpers for the Streamlit app (unit-tested; no streamlit import here)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..verifier import _find_record, _walk

UNK = "unknown"


def _u(x: Any) -> Any:
    return UNK if x is None else x


def accounts_rows(d) -> list[dict]:
    sl = d.companies[: d.brief.max_target_accounts] if d.brief else d.companies
    return [{"rank": i, "company": c.name, "id": _u(c.company_id), "domain": _u(c.domain), "headcount": _u(c.employee_count),
             "growth_6m_%": _u(None if c.headcount_growth_6m is None else round(c.headcount_growth_6m, 1)),
             "open_roles": _u(c.open_roles), "fit": _u(c.fit_score), "coverage": c.data_coverage, "confidence": c.confidence,
             "wave": c.wave or "out of ICP", "buyer": c.buyer_status, "verified": c.verification_status,
             "unknown": ", ".join(f[8:] for f in c.flags if f.startswith("unknown:")) or "-"}
            for i, c in enumerate(sl, 1)]


def breakdown_rows(c) -> list[dict]:
    from ..scoring import WEIGHTS
    return [{"component": k, "max": WEIGHTS[k], "points": _u(c.score_breakdown.get(k))} for k in WEIGHTS]


def tool_run_rows(d) -> list[dict]:
    return [{"run": r.run_id, "tool": r.tool_name, "status": r.result_status, "http": _u(r.http_status), "attempt": r.attempt,
             "ms": r.duration_ms, "credits": _u(r.credit_cost), "results": _u(r.result_count), "total_count": _u(r.total_count),
             "error": r.error_type or "-", "request": r.request_summary[:140]} for r in d.tool_runs]


def competitor_rows(d) -> list[dict]:
    return [{"competitor": c.name, "class": c.classification, "domain": _u(c.domain), "positioning (provider text)": _u(c.positioning_claim),
             "headcount": _u(c.employee_count), "evidence": ", ".join(c.evidence_ids)} for c in d.competitors]


def buyer_rows(d) -> list[dict]:
    rows = []
    for c in (d.companies[: d.brief.max_target_accounts] if d.brief else d.companies):
        plist = d.people.get(c.company_id or "", [])
        for p in plist:
            rows.append({"account": c.name, "person": p.name, "title": _u(p.current_title), "role matched": _u(p.role_matched),
                         "employer verified": f"yes ({p.verification_method})" if p.employer_verified else "no",
                         "flags": ", ".join(p.missing_flags)})
        if not plist and c.buyer_status == "buyer_not_found":
            rows.append({"account": c.name, "person": UNK, "title": UNK, "role matched": UNK, "employer verified": "-",
                         "flags": "buyer_not_found"})
    return rows


def evidence_rows(d, subject_id: str | None = None) -> list[dict]:
    return [{"id": e.evidence_id, "claim": e.claim, "status": e.status, "field_path": _u(e.field_path),
             "retrieved_at": e.retrieved_at_utc, "source": e.source_kind, "contradicts": ", ".join(e.contradiction_with) or "-"}
            for e in d.evidence if subject_id is None or e.subject_id == subject_id]


def source_excerpt(ev) -> dict:
    """What the saved raw response actually holds for this claim (the audit drill-down)."""
    out: dict[str, Any] = {"evidence_id": ev.evidence_id, "claim": ev.claim, "status": ev.status, "notes": ev.notes,
                           "field_path": ev.field_path, "retrieved_at_utc": ev.retrieved_at_utc, "raw_file": ev.raw_ref,
                           "claimed_value": ev.value_observed}
    if not ev.raw_ref:
        return {**out, "value_in_source": None, "note": "no saved source response"}
    try:
        body = json.loads(Path(ev.raw_ref).read_text()).get("body")
    except (OSError, ValueError):
        return {**out, "value_in_source": None, "note": "source file unavailable"}
    rec = _find_record(body, ev)
    if rec is None:
        return {**out, "value_in_source": None, "note": "cited record not found in source"}
    import re
    path = re.sub(r"^results\[\d+\]\.", "", ev.field_path or "")
    return {**out, "value_in_source": _walk(rec, path) if path else None, "source_record_id": ev.source_record_id}


def crm_view(crm_path: str, mission_id: str) -> dict[str, list[dict]]:
    from ..crm import CRM
    crm = CRM(crm_path)
    try:
        comp = [{k: r[k] for k in ("id", "name", "domain", "segment", "stage", "fit_score", "coverage_score", "verification_status")}
                for r in crm.rows("companies", mission_id)]
        tasks = [{k: r[k] for k in ("id", "company_id", "task_type", "status", "title", "draft_text")} for r in crm.rows("crm_tasks", mission_id)]
        people = [{k: r[k] for k in ("id", "name", "title", "company_id", "verified_employment")} for r in crm.rows("people", mission_id)]
        return {"companies": comp, "people": people, "crm_tasks": tasks, "segments": crm.rows("segments", mission_id),
                "counts": [crm.counts(mission_id)]}
    finally:
        crm.close()
