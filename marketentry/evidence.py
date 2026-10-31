"""Evidence ledger: sequential ids, one list per mission."""
from __future__ import annotations

from datetime import datetime, timezone

from .contracts import Evidence


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceLedger:
    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.items: list[Evidence] = []

    def add(self, **kw) -> Evidence:
        kw.setdefault("retrieved_at_utc", utcnow())
        ev = Evidence(evidence_id=f"ev_{len(self.items) + 1:04d}", mission_id=self.mission_id, **kw)
        self.items.append(ev)
        return ev

    def get(self, evidence_id: str) -> Evidence | None:
        return next((e for e in self.items if e.evidence_id == evidence_id), None)
