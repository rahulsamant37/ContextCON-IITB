"""Raw Crustdata JSON -> internal records. The ONLY module that knows provider field paths
(see docs/crustdata_schema_notes.md). Absent / empty / wrong-typed => None."""
from __future__ import annotations

import re
from typing import Any

from .contracts import CompanyRecord, Evidence, IdentityMatch, PersonRecord
from .evidence import EvidenceLedger

# internal field -> (kind, candidate provider paths in priority order)
COMPANY_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "name": ("text", ("basic_info.name",)),
    "domain": ("text", ("basic_info.primary_domain",)),
    "linkedin_url": ("text", ("basic_info.professional_network_url",)),
    "description": ("text", ("basic_info.description",)),
    "employee_range": ("text", ("basic_info.employee_count_range",)),
    "country": ("text", ("locations.country",)),
    "hq_location": ("text", ("locations.headquarters",)),
    "industry": ("text", ("taxonomy.professional_network_industry",)),
    "employee_count": ("int", ("headcount.total",)),
    # search uses 6m/12m, enrich uses six_months/yoy
    "headcount_growth_6m": ("num", ("headcount.growth_percent.6m", "headcount.growth_percent.six_months")),
    "headcount_growth_12m": ("num", ("headcount.growth_percent.12m", "headcount.growth_percent.yoy")),
    "open_roles": ("int", ("hiring.openings_count",)),
    "funding_total": ("num", ("funding.total_investment_usd",)),
    "last_funding_date": ("text", ("funding.last_fundraise_date",)),
}
CLAIM_LABEL = {
    "name": "Company name", "domain": "Primary domain", "country": "HQ country (provider code)",
    "industry": "Industry", "employee_count": "Headcount (total)", "employee_range": "Employee range",
    "headcount_growth_6m": "6-month headcount growth %", "headcount_growth_12m": "12-month headcount growth %",
    "open_roles": "Open roles", "funding_total": "Total funding (USD)", "last_funding_date": "Last fundraise date",
    "linkedin_url": "Professional-network URL", "hq_location": "HQ location", "description": "Description",
}
COVERAGE_FIELDS = ("domain", "country", "industry", "employee_count", "headcount_growth_6m",
                   "open_roles", "funding_total", "description")
# fields whose provider path is compared/merged across search+enrich
_MERGE_CONFLICT_FIELDS = ("employee_count", "headcount_growth_6m", "headcount_growth_12m", "domain")


# ---- helpers ---------------------------------------------------------------
def dig(d: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d


def _coerce(kind: str, v: Any) -> Any:
    if v is None or isinstance(v, bool):
        return None
    if kind == "text":
        return v.strip() or None if isinstance(v, str) else None
    if kind == "int":
        return int(v) if isinstance(v, (int, float)) and float(v).is_integer() else None
    if kind == "num":
        return float(v) if isinstance(v, (int, float)) else None
    return None


def extract_company_fields(raw: dict) -> dict[str, tuple[Any, str]]:
    """internal field -> (value, provider path used). Only non-null values are returned."""
    out: dict[str, tuple[Any, str]] = {}
    for field, (kind, paths) in COMPANY_FIELDS.items():
        for p in paths:
            v = _coerce(kind, dig(raw, p))
            if v is not None:
                out[field] = (v, p)
                break
    return out


def domain_from_url(u: str | None) -> str | None:
    if not u or not isinstance(u, str):
        return None
    u = re.sub(r"^[a-z]+://", "", u.strip().lower())
    u = u.split("/")[0].split("?")[0]
    u = u[4:] if u.startswith("www.") else u
    return u or None


def company_id_of(raw: dict) -> str | None:
    v = raw.get("crustdata_company_id")
    if v is None:
        v = dig(raw, "basic_info.crustdata_company_id")
    return str(v) if isinstance(v, (int, str)) and not isinstance(v, bool) and str(v) else None


# ISO alpha-3 (what responses return) vs the names briefs use. Small, explicit table; unknown => no match.
_COUNTRY_NAMES = {
    "GBR": {"united kingdom", "uk", "great britain", "england", "gb"},
    "USA": {"united states", "usa", "us", "united states of america"},
    "IND": {"india", "in"}, "DEU": {"germany", "de"}, "FRA": {"france", "fr"}, "SGP": {"singapore", "sg"},
    "CAN": {"canada", "ca"}, "AUS": {"australia", "au"}, "NLD": {"netherlands", "nl"},
    "ARE": {"united arab emirates", "uae", "ae"}, "IRL": {"ireland", "ie"}, "ESP": {"spain", "es"},
    "BRA": {"brazil", "br"}, "JPN": {"japan", "jp"}, "SWE": {"sweden", "se"}, "CHE": {"switzerland", "ch"},
}


def country_matches(brief_country: str | None, record_country: str | None) -> bool | None:
    """True/False when decidable, None when either side is unknown or the code is not in the table."""
    if not brief_country or not record_country:
        return None
    b, r = brief_country.strip().lower(), record_country.strip().lower()
    if b == r:
        return True
    names = _COUNTRY_NAMES.get(record_country.strip().upper())
    if names is None:
        return None
    return b in names or b.upper() == record_country.strip().upper()


# ---- companies -------------------------------------------------------------
def coverage(rec: CompanyRecord) -> float:
    return round(sum(getattr(rec, f) is not None for f in COVERAGE_FIELDS) / len(COVERAGE_FIELDS), 3)


def normalize_company(raw: dict, *, enriched: bool = False, ledger: EvidenceLedger | None = None,
                      source_kind: str = "crustdata_company_search", raw_ref: str | None = None,
                      retrieved_at: str | None = None) -> CompanyRecord:
    """raw = a search `companies[]` item or an enrich/identify `company_data`."""
    fields = extract_company_fields(raw)
    cid = company_id_of(raw)
    rec = CompanyRecord(
        company_id=cid,
        name=fields["name"][0] if "name" in fields else (cid and f"unknown (id {cid})") or "unknown",
        enriched=enriched,
        identity=(IdentityMatch(method="company_id", confidence=1.0,
                                decision_note=f"provider record id {cid} from {source_kind}")
                  if cid else IdentityMatch(method="unresolved", decision_note="no crustdata_company_id in record")),
        flags=[] if "name" in fields else ["name_missing"],
        **{f: v for f, (v, _) in fields.items() if f != "name"},
    )
    if cid is None:
        rec.flags.append("no_canonical_id")
    rec.data_coverage = coverage(rec)
    if ledger is not None:
        for ev in company_evidence(raw, rec, ledger, source_kind=source_kind, raw_ref=raw_ref, retrieved_at=retrieved_at):
            rec.evidence_ids.append(ev.evidence_id)
    return rec


def company_evidence(raw: dict, rec: CompanyRecord, ledger: EvidenceLedger, *, source_kind: str,
                     raw_ref: str | None, retrieved_at: str | None) -> list[Evidence]:
    """One Evidence per non-null extracted field; status is `supported` because the value was read from the response."""
    out = []
    for field, (value, path) in extract_company_fields(raw).items():
        extra = {"retrieved_at_utc": retrieved_at} if retrieved_at else {}
        out.append(ledger.add(
            subject_type="company", subject_id=rec.company_id or rec.name,
            claim=f"{CLAIM_LABEL.get(field, field)}: {value}", source_kind=source_kind,
            source_record_id=rec.company_id, field_path=path, raw_ref=raw_ref,
            value_observed=str(value), status="supported", notes="provider-reported", **extra))
    return out


def merge_company(base: CompanyRecord, newer: CompanyRecord) -> CompanyRecord:
    """Overlay `newer` (e.g. enrich) on `base` (e.g. search). Non-null newer wins; disagreements are flagged."""
    if base.company_id and newer.company_id and base.company_id != newer.company_id:
        raise ValueError(f"refusing to merge different companies {base.company_id} / {newer.company_id}")
    merged = base.model_copy(deep=True)
    for field in COMPANY_FIELDS:
        nv, bv = getattr(newer, field), getattr(base, field)
        if nv is None:
            continue
        if field in _MERGE_CONFLICT_FIELDS and bv is not None and bv != nv:
            merged.flags.append(f"conflict:{field}:{bv}->{nv}")
        setattr(merged, field, nv)
    merged.enriched = base.enriched or newer.enriched
    merged.evidence_ids = list(dict.fromkeys(base.evidence_ids + newer.evidence_ids))
    merged.flags = list(dict.fromkeys(merged.flags + newer.flags))
    merged.data_coverage = coverage(merged)
    return merged


def resolve_identify_entry(entry: dict, *, expected_domain: str | None = None,
                           min_confidence: float = 0.9, **norm_kw) -> tuple[CompanyRecord | None, IdentityMatch]:
    """Decide whether an identify/enrich envelope entry maps to ONE company we can trust.
    Name-only matches are never accepted (live: names=['Bits'] -> a university at confidence 1.0)."""
    cands = sorted(((m.get("confidence_score") or 0.0, m.get("company_data") or {})
                    for m in (entry.get("matches") or []) if isinstance(m, dict)),
                   key=lambda c: -c[0])
    if not cands:
        return None, IdentityMatch(method="unresolved", decision_note="no match returned")
    mtype = entry.get("match_type")
    summary = "; ".join(f"{dig(c, 'basic_info.name')} <{dig(c, 'basic_info.primary_domain')}> "
                        f"id={company_id_of(c)} conf={s}" for s, c in cands[:3])

    if expected_domain:
        want = domain_from_url(expected_domain)
        hit = next(((s, c) for s, c in cands if domain_from_url(dig(c, "basic_info.primary_domain")) == want), None)
        if hit is None:
            return None, IdentityMatch(method="unresolved", decision_note=f"no candidate has domain {want}: {summary}")
        s, c = hit
        return normalize_company(c, **norm_kw), IdentityMatch(
            method="domain", confidence=float(s), decision_note=f"candidate domain equals expected {want}")

    top_s, top_c = cands[0]
    tied = [c for s, c in cands if s == top_s]
    if mtype not in ("crustdata_company_id", "domain"):
        return None, IdentityMatch(method="unresolved", confidence=float(top_s),
                                   decision_note=f"{mtype} match needs domain verification: {summary}")
    if top_s < min_confidence:
        return None, IdentityMatch(method="unresolved", confidence=float(top_s),
                                   decision_note=f"confidence below {min_confidence}: {summary}")
    if len(tied) > 1:
        return None, IdentityMatch(method="unresolved", confidence=float(top_s),
                                   decision_note=f"ambiguous: {len(tied)} candidates tie: {summary}")
    method = "company_id" if mtype == "crustdata_company_id" else "domain"
    return normalize_company(top_c, **norm_kw), IdentityMatch(
        method=method, confidence=float(top_s), decision_note=f"unique {mtype} match: {summary}")


def unwrap_envelope(body: Any) -> list[dict]:
    """identify/enrich response -> list of entries (empty if the shape is unexpected)."""
    return [e for e in body if isinstance(e, dict)] if isinstance(body, list) else []


# ---- people ----------------------------------------------------------------
_ABBREV = {"ciso": "chief information security officer", "cto": "chief technology officer",
           "ceo": "chief executive officer", "cfo": "chief financial officer", "coo": "chief operating officer",
           "cio": "chief information officer", "cro": "chief risk officer", "vp": "vice president",
           "svp": "senior vice president", "evp": "executive vice president"}
_STOP = {"of", "the", "and", "for", "&", "at"}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    expanded: list[str] = []
    for w in words:
        expanded.extend(_ABBREV.get(w, w).split())
    return {w for w in expanded if w not in _STOP}


def match_role(title: str | None, roles: list[str]) -> str | None:
    """First target role whose tokens are all present in the title (abbreviations expanded)."""
    if not title:
        return None
    t = _tokens(title)
    for role in roles:
        r = _tokens(role)
        if r and r <= t:
            return role
    return None


def normalize_person(raw: dict, company: CompanyRecord, target_roles: list[str], *,
                     ledger: EvidenceLedger | None = None, source_kind: str = "crustdata_person_search",
                     raw_ref: str | None = None, retrieved_at: str | None = None) -> PersonRecord:
    """Employer is verified against `company` by crustdata_company_id, else by website domain. Emails are never read."""
    pid = raw.get("crustdata_person_id")
    title = _coerce("text", dig(raw, "basic_profile.current_title"))
    currents = [c for c in (dig(raw, "experience.employment_details.current") or []) if isinstance(c, dict)]
    if title is None and currents:
        title = _coerce("text", currents[0].get("title"))

    emp, method = None, "none"
    if company.company_id:
        emp = next((c for c in currents if str(c.get("crustdata_company_id")) == company.company_id), None)
        method = "id" if emp else "none"
    if emp is None and company.domain:
        emp = next((c for c in currents if domain_from_url(c.get("company_website")) == company.domain), None)
        method = "domain" if emp else "none"
    shown = emp or (currents[0] if currents else {})
    emp_cid = shown.get("crustdata_company_id")

    flags = []
    if emp is None:
        flags.append("employer_not_verified")
    if title is None:
        flags.append("title_missing")
    role = match_role(title, target_roles)
    if role is None:
        flags.append("title_not_matching_target_roles")
    start = _coerce("text", shown.get("start_date"))
    if start is None:
        flags.append("employment_start_missing")
    flags.append("linkedin_url_missing")

    rec = PersonRecord(
        person_id=str(pid) if isinstance(pid, (int, str)) and not isinstance(pid, bool) else None,
        company_id=company.company_id,
        name=_coerce("text", dig(raw, "basic_profile.name")) or "unknown",
        headline=_coerce("text", dig(raw, "basic_profile.headline")),
        current_title=title,
        role_matched=role,
        current_employer_name=_coerce("text", shown.get("name")),
        current_employer_company_id=str(emp_cid) if emp_cid is not None else None,
        current_employer_domain=domain_from_url(shown.get("company_website")),
        employment_start=start,
        employer_verified=emp is not None,
        verification_method=method,
        missing_flags=flags,
        verification_status="supported" if emp is not None else "unverified",
    )
    if ledger is not None:
        ts = {"retrieved_at_utc": retrieved_at} if retrieved_at else {}
        sid = rec.person_id or rec.name
        if title:
            rec.evidence_ids.append(ledger.add(
                subject_type="person", subject_id=sid, claim=f"Current title: {title}", source_kind=source_kind,
                source_record_id=rec.person_id, field_path="basic_profile.current_title", raw_ref=raw_ref,
                value_observed=title, status="supported", **ts).evidence_id)
        if emp is not None:
            rec.evidence_ids.append(ledger.add(
                subject_type="person", subject_id=sid,
                claim=f"Currently employed at {rec.current_employer_name} (matched on {method})",
                source_kind=source_kind, source_record_id=rec.person_id,
                field_path="experience.employment_details.current[].crustdata_company_id"
                if method == "id" else "experience.employment_details.current[].company_website",
                raw_ref=raw_ref, value_observed=str(emp_cid if method == "id" else shown.get("company_website")),
                status="supported", **ts).evidence_id)
    return rec
