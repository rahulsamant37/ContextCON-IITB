"""Buyer mapping: Person Search by employer domain + loose title query, then Python decides.
A person is kept only if (1) their current employer is verified against the account's Crustdata ID/domain and
(2) their title matches a target role. No match => buyer_not_found. A failed call => not_searched (never 'not found')."""
from __future__ import annotations

from .contracts import CompanyRecord, MarketBrief, PersonRecord
from .crustdata_client import CrustdataClient
from .evidence import EvidenceLedger
from .normalizers import _ABBREV, _STOP, normalize_person

PERSON_FIELDS = ["basic_profile", "experience.employment_details.current"]
TITLE_PATH = "experience.employment_details.current.title"
DOMAIN_PATH = "experience.employment_details.current.company_website_domain"


def title_variants(role: str) -> list[str]:
    """Query strings for the loose `(.)` title operator: raw words and abbreviation-expanded words."""
    words = [w for w in role.lower().replace(",", " ").split() if w not in _STOP]
    expanded = [x for w in words for x in _ABBREV.get(w, w).split()]
    return list(dict.fromkeys([" ".join(words), " ".join(expanded)]))


def build_person_filters(domain: str, roles: list[str]) -> dict:
    titles = [{"field": TITLE_PATH, "type": "(.)", "value": v} for r in roles for v in title_variants(r) if v]
    return {"op": "and", "conditions": [{"field": DOMAIN_PATH, "type": "=", "value": domain},
                                        {"op": "or", "conditions": titles} if len(titles) > 1 else titles[0]]}


def dedupe_people(people: list[PersonRecord]) -> list[PersonRecord]:
    """The provider can hold several profile records for one person (live: same CEO under two ids). Keep one per
    name, preferring an ID-verified employer, and record the merge so it stays visible."""
    groups: dict[str, list[PersonRecord]] = {}
    for p in people:
        groups.setdefault(p.name.strip().lower(), []).append(p)
    out = []
    for grp in groups.values():
        grp.sort(key=lambda p: (p.verification_method != "id", p.person_id or ""))
        keep, extra = grp[0], grp[1:]
        if extra:
            keep = keep.model_copy(update={"missing_flags": keep.missing_flags + [
                "duplicate_profiles_merged:" + ",".join(e.person_id or "?" for e in extra)]})
        out.append(keep)
    return out


def role_rank(p: PersonRecord, roles: list[str]) -> int:
    return roles.index(p.role_matched) if p.role_matched in roles else len(roles)


def map_buyers(client: CrustdataClient, accounts: list[CompanyRecord], brief: MarketBrief, ledger: EvidenceLedger,
               *, limit: int = 10) -> tuple[dict[str, list[PersonRecord]], dict[str, str], list[str]]:
    """Returns (people by company_id, buyer_status by company_id, warnings). Only `accounts` are searched."""
    people: dict[str, list[PersonRecord]] = {}
    status: dict[str, str] = {}
    warnings: list[str] = []
    for c in accounts:
        if not c.company_id:
            warnings.append(f"buyers: {c.name} has no canonical id; not searched")
            continue
        if not c.domain:
            warnings.append(f"buyers: {c.name} has no domain; person search needs an employer domain")
            continue
        r = client.person_search(build_person_filters(c.domain, brief.target_buyer_roles), PERSON_FIELDS, limit)
        if not r.ok or not isinstance(r.body, dict):
            warnings.append(f"buyers: person search failed for {c.name} ({r.error_type}); buyer status left unknown")
            continue
        kept: list[PersonRecord] = []
        for raw in r.body.get("profiles") or []:
            p = normalize_person(raw, c, brief.target_buyer_roles, ledger=ledger, raw_ref=r.run.raw_path,
                                 retrieved_at=r.retrieved_at)
            if p.employer_verified and p.role_matched:
                kept.append(p)
        kept = dedupe_people(kept)
        kept.sort(key=lambda p: (role_rank(p, brief.target_buyer_roles), p.name))
        kept = kept[: brief.max_contacts_per_company]
        if kept:
            people[c.company_id], status[c.company_id] = kept, "found"
        else:
            status[c.company_id] = "buyer_not_found"
            seen = len(r.body.get("profiles") or [])
            warnings.append(f"buyers: {c.name}: no verified target-role contact ({seen} profiles returned, none matched)")
    return people, status, warnings
