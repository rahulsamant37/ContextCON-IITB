"""Deliverables: Target_Accounts.csv, Buyer_Map.csv, Competitive_Landscape.csv, Evidence_Log.json and the report
(HTML always, PDF when weasyprint works). Unknown values are written as 'unknown', never blank or zero."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ROOT
from .evidence import utcnow

UNK = "unknown"


def _v(x: Any) -> Any:
    return UNK if x is None or x == "" else x


def _refs(ids: list[str]) -> str:
    return ";".join(ids)


def _write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def recommendation(d) -> dict[str, str]:
    """Rule-based (not LLM). Thresholds are stated in the text so the call is auditable."""
    w = {k: sum(c.wave == k for c in d.companies[: d.brief.max_target_accounts]) for k in ("Wave 1", "Wave 2", "Research Needed")}
    total = d.universe.total_count
    if not total:
        return {"verdict": "Do not proceed on this evidence",
                "text": "No indexed companies were found for the scoped filters, or the provider returned no count. No entry decision can be supported."}
    if w["Wave 1"] >= 3:
        v = "Proceed: pilot launch with Wave 1"
    elif w["Wave 1"] + w["Wave 2"] >= 5:
        v = "Proceed cautiously: complete buyer verification first"
    else:
        v = "Defer: insufficient qualified accounts"
    text = (f"Crustdata indexes {total:,} companies matching the scoped filters. Of the {sum(w.values())} shortlisted accounts, "
            f"{w['Wave 1']} are Wave 1 (fit >= 60, verified buyer), {w['Wave 2']} are Wave 2 (fit >= 40) and "
            f"{w['Research Needed']} need research. Rule: Wave 1 >= 3 => proceed; Wave 1 + Wave 2 >= 5 => proceed cautiously; "
            f"otherwise defer. Headcount, growth and hiring are indicators only and do not prove purchase intent.")
    return {"verdict": v, "text": text}


def risks(d) -> list[str]:
    sl = d.companies[: d.brief.max_target_accounts]
    out = ["Company counts come from Crustdata's database, which may not include every business in this market.",
           "Market value is the number of companies found multiplied by your contract value. It is a rough guide, not a revenue forecast.",
           "Public job and company data can be out of date. Check key details before you reach out."]
    nb = sum(c.buyer_status == "buyer_not_found" for c in sl)
    ns = sum(c.buyer_status == "not_searched" for c in sl)
    if nb:
        out.append(f"No decision-maker in your buyer roles was found at {nb} of the companies searched.")
    if ns:
        searched = sum(1 for r in d.tool_runs if r.tool_name == "person_search" and r.result_status in ("ok", "empty", "replayed"))
        out.append(f"{ns} of the shortlisted compan{'y has' if ns == 1 else 'ies have'} not been searched for decision-makers yet. "
                   f"This research searched {searched} compan{'y' if searched == 1 else 'ies'}, highest-ranked first, to keep costs down; "
                   f"companies where a search found no one move down the list.")
    unk = sum(1 for c in sl if "unknown:hiring" in c.flags)
    if unk:
        out.append(f"Hiring activity isn't available for {unk} compan{'y' if unk == 1 else 'ies'}. That means no job data was found, not that they aren't hiring.")
    if d.verification and d.verification.contradictions:
        out.append(f"{len(d.verification.contradictions)} data point(s) differ between sources; both values are kept in the source log.")
    if d.brief.annual_contract_value is None:
        out.append("No contract value was given, so no market value is shown.")
    return out


def export_all(d, out_root: Path | str) -> dict[str, str]:
    assert d.brief is not None
    out = Path(out_root) / d.mission_id
    out.mkdir(parents=True, exist_ok=True)
    sl = d.companies[: d.brief.max_target_accounts]
    by_id = {c.company_id: c for c in d.companies if c.company_id}
    A: dict[str, str] = {}

    _write_csv(out / "Target_Accounts.csv",
               ["rank", "company_name", "crustdata_company_id", "domain", "country_code", "sector_basis", "employee_count",
                "employee_range", "headcount_growth_6m_pct", "open_roles", "total_funding_usd", "fit_score", "data_coverage",
                "confidence", "wave", "buyer_status", "identity_method", "verification_status", "unknown_fields", "flags",
                "evidence_refs"],
               [[i, c.name, _v(c.company_id), _v(c.domain), _v(c.country), d.sector_basis,
                 _v(c.employee_count), _v(c.employee_range),
                 _v(None if c.headcount_growth_6m is None else round(c.headcount_growth_6m, 2)), _v(c.open_roles),
                 _v(c.funding_total), _v(c.fit_score), c.data_coverage, c.confidence, _v(c.wave), c.buyer_status,
                 c.identity.method, c.verification_status,
                 ";".join(f[8:] for f in c.flags if f.startswith("unknown:")), ";".join(c.flags), _refs(c.evidence_ids)]
                for i, c in enumerate(sl, 1)])
    A["Target_Accounts.csv"] = str(out / "Target_Accounts.csv")

    rows = []
    for c in sl:
        plist = d.people.get(c.company_id or "", [])
        if plist:
            for p in plist:
                rows.append([c.name, _v(c.company_id), _v(c.domain), _v(p.person_id), p.name, _v(p.current_title), _v(p.role_matched),
                             _v(p.current_employer_name), _v(p.current_employer_company_id), _v(p.current_employer_domain),
                             p.employer_verified, p.verification_method, p.verification_status, ";".join(p.missing_flags),
                             _refs(p.evidence_ids)])
        elif c.buyer_status != "not_searched":
            rows.append([c.name, _v(c.company_id), _v(c.domain), UNK, UNK, UNK, UNK, UNK, UNK, UNK, False, "none", "unverified",
                         "buyer_not_found", ""])
    _write_csv(out / "Buyer_Map.csv",
               ["company_name", "company_id", "company_domain", "person_id", "person_name", "title", "target_role_matched",
                "current_employer", "employer_company_id", "employer_domain", "employer_verified", "verification_method",
                "verification_status", "missing_data_flags", "evidence_refs"], rows)
    A["Buyer_Map.csv"] = str(out / "Buyer_Map.csv")

    _write_csv(out / "Competitive_Landscape.csv",
               ["competitor", "crustdata_company_id", "domain", "classification", "positioning_claim_provider_description",
                "differentiators", "employee_count", "headcount_growth_6m_pct", "source_url", "evidence_refs"],
               [[c.name, _v(c.company_id), _v(c.domain), c.classification, _v(c.positioning_claim),
                 "not assessed (no product comparison sources fetched)", _v(c.employee_count),
                 _v(None if c.headcount_growth_6m is None else round(c.headcount_growth_6m, 2)), _v(c.source_url),
                 _refs(c.evidence_ids)] for c in d.competitors])
    A["Competitive_Landscape.csv"] = str(out / "Competitive_Landscape.csv")

    log = {
        "mission_id": d.mission_id, "generated_at_utc": utcnow(), "state": d.state,
        "verified_claim_fraction": d.verified_claim_fraction,
        "verification_counts": d.verification.counts if d.verification else None,
        "contradictions": d.verification.contradictions if d.verification else [],
        "assumptions": [a.model_dump() for a in d.brief.assumptions],
        "unsupported_constraints": d.brief.unsupported_constraints,
        "universe": d.universe.model_dump(), "sizing": d.sizing.model_dump(),
        "evidence": [e.model_dump() for e in d.evidence],
        "tool_runs": [r.model_dump() for r in d.tool_runs],  # request summaries contain filters only; never headers/keys
        "warnings": d.warnings,
    }
    (out / "Evidence_Log.json").write_text(json.dumps(log, indent=2, ensure_ascii=False, default=str))
    A["Evidence_Log.json"] = str(out / "Evidence_Log.json")

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    waves = {k: [c for c in sl if c.wave == k] for k in ("Wave 1", "Wave 2", "Research Needed")}
    html = env.get_template("report.html.j2").render(
        d=d, brief=d.brief, sl=sl, waves=waves, rec=recommendation(d), risks=risks(d), people=d.people, by_id=by_id,
        generated=utcnow(), credits=d.credit_used, n_calls=sum(1 for r in d.tool_runs if r.result_status in ("ok", "empty")))
    (out / "Market_Entry_Report.html").write_text(html, encoding="utf-8")
    A["Market_Entry_Report.html"] = str(out / "Market_Entry_Report.html")
    try:
        import weasyprint
        weasyprint.HTML(string=html, base_url=str(out)).write_pdf(str(out / "Market_Entry_Report.pdf"))
        A["Market_Entry_Report.pdf"] = str(out / "Market_Entry_Report.pdf")
    except Exception as e:  # HTML report remains valid, printable to PDF
        d.warnings.append(f"PDF rendering unavailable ({type(e).__name__}); HTML report can be printed to PDF")
    return A
