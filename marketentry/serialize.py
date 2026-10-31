"""MissionData -> JSON documents on disk (replaces trusting pickles for the web app).
out/<mission>/mission.json  full payload   |  summary.json  small card for the history list  |  events.json  run trace."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exporters import recommendation, risks

SAFE_NAME = __import__("re").compile(r"^mission_[0-9a-f]{10}$")


def valid_mission_id(mid: str) -> bool:
    return bool(SAFE_NAME.match(mid))


def mission_payload(d) -> dict[str, Any]:
    """Everything the dashboard needs. Pydantic objects are dumped in JSON mode (no secrets are ever in MissionData)."""
    b = d.brief
    sl = d.companies[: b.max_target_accounts] if b else d.companies
    waves = {k: sum(c.wave == k for c in sl) for k in ("Wave 1", "Wave 2", "Research Needed")}
    rec = recommendation(d) if b else {"verdict": "No brief", "text": ""}
    return {
        "mission_id": d.mission_id, "state": d.state, "started_at": d.started_at, "finished_at": d.finished_at,
        "brief": b.model_dump(mode="json") if b else None,
        "steps": [s.model_dump(mode="json") for s in d.steps],
        "universe": d.universe.model_dump(mode="json"), "sizing": d.sizing.model_dump(mode="json"),
        "sector_basis": d.sector_basis, "recommendation": rec, "risks": risks(d) if b else [], "waves": waves,
        "accounts": [{"rank": i, **c.model_dump(mode="json")} for i, c in enumerate(sl, 1)],
        "people": {k: [p.model_dump(mode="json") for p in v] for k, v in d.people.items()},
        "competitors": [c.model_dump(mode="json") for c in d.competitors],
        "evidence": [e.model_dump(mode="json") for e in d.evidence],
        "tool_runs": [r.model_dump(mode="json") for r in d.tool_runs],
        "llm_runs": d.llm_runs, "warnings": d.warnings,
        "verification": ({"counts": d.verification.counts, "contradictions": d.verification.contradictions,
                          "arithmetic_errors": d.verification.arithmetic_errors, "checked": d.verification.checked}
                         if d.verification else None),
        "verified_claim_fraction": d.verified_claim_fraction, "credit_used": d.credit_used,
        "artifacts": sorted(Path(p).name for p in d.artifacts.values()),
        "crm_counts": d.crm_counts,
    }


def summary_card(d) -> dict[str, Any]:
    b = d.brief
    return {"mission_id": d.mission_id, "state": d.state, "created_at": d.started_at,
            "prompt": b.raw_prompt if b else "", "country": b.target_country if b else None,
            "industry": b.target_industry if b else None, "product": b.product_description if b else None,
            "accounts": len(d.companies[: b.max_target_accounts]) if b else 0,
            "wave1": sum(c.wave == "Wave 1" for c in d.companies[: b.max_target_accounts]) if b else 0,
            "indexed_count": d.universe.total_count, "credits": d.credit_used,
            "verified_fraction": d.verified_claim_fraction, "currency": b.currency if b else None,
            "pool": d.sizing.pool}


def save_mission(d, out_dir: Path | str, events: list[dict] | None = None) -> None:
    if not d.mission_id:
        return
    folder = Path(out_dir) / d.mission_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mission.json").write_text(json.dumps(mission_payload(d), ensure_ascii=False, default=str))
    (folder / "summary.json").write_text(json.dumps(summary_card(d), ensure_ascii=False, default=str))
    if events is not None:
        (folder / "events.json").write_text(json.dumps(events, ensure_ascii=False, default=str))


def load_json(out_dir: Path | str, mission_id: str, name: str) -> Any | None:
    if not valid_mission_id(mission_id):
        return None
    p = Path(out_dir) / mission_id / name
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def list_summaries(out_dir: Path | str) -> list[dict]:
    out = []
    for p in Path(out_dir).glob("mission_*/summary.json"):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda s: s.get("created_at") or "", reverse=True)
