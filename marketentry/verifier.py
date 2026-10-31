"""Evidence verifier. Deterministic and local: re-opens each saved raw response and checks that the cited record
(by canonical id) really contains the claimed value at the cited path; flags stale data and contradictions;
recomputes every number. Unverifiable claims become `unverified`/`unsupported`, never silently dropped."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import CompanyRecord, Evidence, MarketBrief, PersonRecord, SizingResult
from .evidence import EvidenceLedger
from .scoring import score_company
from .sizing import verify_sizing

MAX_AGE_HOURS = 72.0
_SEVERITY = ["supported", "unverified", "stale", "conflicting", "unsupported"]  # worst last


@dataclass
class VerificationReport:
    checked: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    contradictions: list[str] = field(default_factory=list)
    arithmetic_errors: list[str] = field(default_factory=list)
    score_mismatches: list[str] = field(default_factory=list)
    duplicate_accounts: list[str] = field(default_factory=list)
    verified_fraction: float | None = None

    def warnings(self) -> list[str]:
        out = []
        bad = {k: v for k, v in self.counts.items() if k != "supported" and v}
        if bad:
            out.append("verifier: non-supported claims " + ", ".join(f"{k}={v}" for k, v in sorted(bad.items())))
        out += [f"verifier: contradiction {c}" for c in self.contradictions[:5]]
        out += [f"verifier: arithmetic {e}" for e in self.arithmetic_errors]
        out += [f"verifier: score mismatch {e}" for e in self.score_mismatches]
        out += [f"verifier: duplicate account {e}" for e in self.duplicate_accounts]
        return out


def _walk(obj: Any, path: str) -> list[Any]:
    """Resolve a dotted path; `name[]` fans out over a list. Returns all reachable values (may be empty)."""
    cur = [obj]
    for part in path.split("."):
        nxt = []
        fan = part.endswith("[]")
        key = part[:-2] if fan else part
        for c in cur:
            if isinstance(c, dict) and key in c:
                v = c[key]
                nxt.extend(v if fan and isinstance(v, list) else [v])
        cur = nxt
    return cur


def _equal(observed: str | None, actual: Any) -> bool:
    if observed is None:
        return actual is None
    try:
        return float(observed) == float(actual) and not isinstance(actual, bool)
    except (TypeError, ValueError):
        pass
    return str(actual) == observed or (isinstance(actual, str) and actual.strip() == observed)


def _find_record(body: Any, ev: Evidence) -> Any | None:
    sid = ev.source_record_id
    if ev.subject_type == "market":
        return body if isinstance(body, dict) else None
    if ev.source_kind == "crustdata_web_search":
        m = re.match(r"results\[(\d+)\]", ev.field_path or "")
        res = body.get("results") if isinstance(body, dict) else None
        return res[int(m.group(1))] if m and isinstance(res, list) and int(m.group(1)) < len(res) else None
    if isinstance(body, dict):
        for k in ("companies", "profiles"):
            for item in body.get(k) or []:
                if isinstance(item, dict) and sid is not None and str(item.get("crustdata_company_id", item.get("crustdata_person_id"))) == sid:
                    return item
    if isinstance(body, list):
        for entry in body:
            for m in (entry.get("matches") or []) if isinstance(entry, dict) else []:
                data = (m.get("company_data") or m.get("person_data") or {}) if isinstance(m, dict) else {}
                cid = data.get("crustdata_company_id", data.get("crustdata_person_id"))
                if sid is not None and cid is not None and str(cid) == sid:
                    return data
    return None


def _age_hours(ts: str) -> float | None:
    try:
        t = datetime.fromisoformat(ts)
        return (datetime.now(timezone.utc) - (t if t.tzinfo else t.replace(tzinfo=timezone.utc))).total_seconds() / 3600
    except ValueError:
        return None


def check_evidence(ev: Evidence, cache: dict[str, Any], max_age_hours: float) -> tuple[str, str]:
    """(status, note). Only reads local saved responses."""
    if not ev.raw_ref:
        return "unverified", "no saved source response referenced"
    p = Path(ev.raw_ref)
    if ev.raw_ref not in cache:
        try:
            cache[ev.raw_ref] = json.loads(p.read_text()).get("body")
        except (OSError, ValueError):
            cache[ev.raw_ref] = None
    body = cache[ev.raw_ref]
    if body is None:
        return "unverified", f"source file unavailable: {ev.raw_ref}"
    rec = _find_record(body, ev)
    if rec is None:
        return "unsupported", "cited record not found in the saved response (identity/source mismatch)"
    if not ev.field_path:
        return "unverified", "no field path to check"
    path = re.sub(r"^results\[\d+\]\.", "", ev.field_path)
    vals = _walk(rec, path)
    if not vals:
        return "unsupported", f"field {ev.field_path} absent in cited record"
    web = ev.source_kind == "crustdata_web_search"  # snippets are stored truncated to 300 chars
    if not any((str(v)[:300] == ev.value_observed) if web else _equal(ev.value_observed, v) for v in vals):
        return "unsupported", f"claimed {ev.value_observed!r} but source has {vals[:3]!r}"
    age = _age_hours(ev.retrieved_at_utc)
    if age is not None and age > max_age_hours:
        return "stale", f"retrieved {age:.0f}h ago (> {max_age_hours:.0f}h)"
    return "supported", "value found in cited record"


def find_contradictions(items: list[Evidence]) -> list[str]:
    """Same subject, same measured quantity, different observed values across evidence records."""
    seen: dict[tuple[str, str], Evidence] = {}
    out = []
    for e in items:
        if e.status not in ("supported", "stale") or e.subject_type not in ("company", "person"):
            continue
        key = (e.subject_id, e.claim.split(":")[0])
        prev = seen.get(key)
        if prev is None:
            seen[key] = e
        elif prev.value_observed != e.value_observed and not _equal(prev.value_observed, e.value_observed):
            for a, b in ((prev, e), (e, prev)):
                a.status = "conflicting"
                a.contradiction_with = sorted(set(a.contradiction_with + [b.evidence_id]))
            out.append(f"{e.subject_id} {key[1]}: {prev.value_observed} ({prev.evidence_id}) vs {e.value_observed} ({e.evidence_id})")
    return out


def rollup(ids: list[str], by_id: dict[str, Evidence]) -> str:
    sts = [by_id[i].status for i in ids if i in by_id]
    if not sts:
        return "unverified"
    return max(sts, key=lambda s: _SEVERITY.index(s) if s in _SEVERITY else 1)


def verify_mission(brief: MarketBrief, ledger: EvidenceLedger, companies: list[CompanyRecord],
                   people: dict[str, list[PersonRecord]], sizing: SizingResult, shortlist_eligible: int,
                   *, max_age_hours: float = MAX_AGE_HOURS, sector_by_filter: bool = True) -> VerificationReport:
    rep = VerificationReport()
    cache: dict[str, Any] = {}
    for ev in ledger.items:
        if ev.subject_type == "calc":
            continue
        ev.status, note = check_evidence(ev, cache, max_age_hours)  # type: ignore[assignment]
        ev.notes = f"{ev.notes}; verifier: {note}".strip("; ")
    rep.contradictions = find_contradictions(ledger.items)

    # arithmetic is recomputed, not trusted
    rep.arithmetic_errors = verify_sizing(sizing, shortlist_eligible)
    if sizing.acv is not None:
        ledger.add(subject_type="calc", subject_id="sizing", claim=f"Sizing arithmetic: {sizing.formula_text.replace(chr(10), ' | ')}",
                   source_kind="python_recompute", value_observed=str(sizing.pool),
                   status="unsupported" if rep.arithmetic_errors else "supported",
                   notes="recomputed from observed count x client-supplied ACV" + (f"; errors: {rep.arithmetic_errors}" if rep.arithmetic_errors else ""))
    for c in companies:
        again = score_company(c, brief, sector_matched_by_filter=sector_by_filter)
        if again.fit_score != c.fit_score:
            rep.score_mismatches.append(f"{c.name}: stored {c.fit_score} vs recomputed {again.fit_score}")
    keys = [c.company_id or c.domain or c.name.lower() for c in companies]
    rep.duplicate_accounts = sorted({k for k in keys if keys.count(k) > 1})

    by_id = {e.evidence_id: e for e in ledger.items}
    for c in companies:
        c.verification_status = rollup(c.evidence_ids, by_id)  # type: ignore[assignment]
    for plist in people.values():
        for p in plist:
            p.verification_status = rollup(p.evidence_ids, by_id)  # type: ignore[assignment]

    rep.checked = len(ledger.items)
    for e in ledger.items:
        rep.counts[e.status] = rep.counts.get(e.status, 0) + 1
    rep.verified_fraction = round(rep.counts.get("supported", 0) / rep.checked, 4) if rep.checked else None
    return rep
