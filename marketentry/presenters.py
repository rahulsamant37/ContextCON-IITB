"""Read-side helpers shared by the API: score breakdown rows and the evidence drill-down."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .contracts import CompanyRecord, Evidence
from .scoring import WEIGHTS
from .verifier import _find_record, _walk

UNK = "unknown"


def breakdown_rows(c: CompanyRecord) -> list[dict]:
    """Rubric components with points earned, or 'unknown' when there was no observed evidence."""
    return [{"component": k, "max": WEIGHTS[k], "points": UNK if c.score_breakdown.get(k) is None else c.score_breakdown[k]}
            for k in WEIGHTS]


def source_excerpt(ev: Evidence) -> dict[str, Any]:
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
    path = re.sub(r"^results\[\d+\]\.", "", ev.field_path or "")
    return {**out, "value_in_source": _walk(rec, path) if path else None, "source_record_id": ev.source_record_id}
