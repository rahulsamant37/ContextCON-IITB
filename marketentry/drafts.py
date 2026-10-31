"""CRM task plan + UNSENT outreach drafts. Drafts only use observed, evidence-backed facts, never contain
contact details, and are stored with status 'draft_unsent'. The LLM may polish wording but is validated."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .contracts import CompanyRecord, Evidence, MarketBrief, PersonRecord
from .crm import account_key, person_key
from .llm import LLMClient

FOOTER = "[DRAFT — UNSENT. Stored locally only; not sent to any external party.]"


@dataclass
class TaskSpec:
    task_key: str
    account_key: str | None
    task_type: str
    title: str
    status: str
    draft_text: str | None = None


def observed_facts(c: CompanyRecord, evidence: dict[str, Evidence]) -> list[tuple[str, str]]:
    """(sentence, evidence_id) pairs; only fields with an Evidence record are eligible."""
    by_path = {evidence[e].field_path: evidence[e] for e in c.evidence_ids if e in evidence}
    facts: list[tuple[str, str]] = []
    if c.headcount_growth_6m is not None and c.headcount_growth_6m > 0 and "headcount.growth_percent.6m" in by_path:
        facts.append((f"{c.name}'s headcount grew about {c.headcount_growth_6m:.0f}% over the last six months",
                      by_path["headcount.growth_percent.6m"].evidence_id))
    elif c.headcount_growth_6m is not None and c.headcount_growth_6m > 0 and "headcount.growth_percent.six_months" in by_path:
        facts.append((f"{c.name}'s headcount grew about {c.headcount_growth_6m:.0f}% over the last six months",
                      by_path["headcount.growth_percent.six_months"].evidence_id))
    if c.open_roles and "hiring.openings_count" in by_path:
        facts.append((f"{c.name} currently lists {c.open_roles} open roles", by_path["hiring.openings_count"].evidence_id))
    if c.employee_count and "headcount.total" in by_path:
        facts.append((f"{c.name} has roughly {c.employee_count} people", by_path["headcount.total"].evidence_id))
    return facts[:2]


def template_draft(c: CompanyRecord, person: PersonRecord | None, brief: MarketBrief,
                   evidence: dict[str, Evidence]) -> tuple[str, list[str]]:
    facts = observed_facts(c, evidence)
    who = person.name.split()[0] if person and person.name != "unknown" else "there"
    obs = (" " + "; ".join(f for f, _ in facts) + ".") if facts else ""
    body = (f"Hi {who},\n\nI'm exploring how {brief.product_description} could help teams like {c.name} in "
            f"{brief.target_country}.{obs} If this is relevant to your remit"
            f"{' as ' + person.current_title if person and person.current_title else ''}, "
            f"I'd welcome a short conversation.\n\n{FOOTER}")
    return body, [e for _, e in facts]


def _safe_polish(template: str, facts: list[str], llm: LLMClient | None) -> str | None:
    """LLM rewrite is accepted only if it adds no numbers, links, or contact details beyond the template."""
    if llm is None or not llm.available:
        return None
    out = llm.complete_text(
        "Rewrite the outreach draft in at most 90 words, warm and plain. Keep every fact and the final bracketed "
        "footer line unchanged. Add no new facts, numbers, links, or contact details.", template, purpose="draft_polish")
    if not out or FOOTER not in out or re.search(r"https?://|www\.|@", out):
        return None
    allowed = set(re.findall(r"\d+", template))
    return out if set(re.findall(r"\d+", out)) <= allowed else None


def plan_tasks(companies: list[CompanyRecord], people: dict[str, list[PersonRecord]], brief: MarketBrief,
               evidence: dict[str, Evidence], llm: LLMClient | None = None) -> list[TaskSpec]:
    """people is keyed by company_id (or account_key for unresolved)."""
    specs: list[TaskSpec] = [
        TaskSpec("mission|checklist|acv", None, "launch_checklist", "Confirm the client-supplied ACV and currency before sharing sizing", "todo"),
        TaskSpec("mission|checklist|buyers", None, "launch_checklist", "Manually verify buyer identities before any outreach", "todo"),
        TaskSpec("mission|checklist|coverage", None, "launch_checklist", "Review accounts flagged 'unknown:*' and unresolved identities", "todo"),
    ]
    for c in companies:
        if c.wave is None:
            continue
        ak = account_key(c)
        contacts = [p for p in people.get(c.company_id or ak, []) if p.employer_verified][: brief.max_contacts_per_company]
        if c.wave == "Research Needed":
            gaps = ", ".join(f[8:] for f in c.flags if f.startswith("unknown:")) or "identity/fit evidence"
            specs.append(TaskSpec(f"{ak}|research", ak, "research", f"Complete research for {c.name}: missing {gaps}", "todo"))
            continue
        specs.append(TaskSpec(f"{ak}|qualify", ak, "qualify", f"Review evidence and fit for {c.name} ({c.wave})", "todo"))
        if not contacts:
            specs.append(TaskSpec(f"{ak}|find_buyer", ak, "research", f"Find a verified buyer at {c.name} (none found)", "todo"))
        for p in contacts:
            text, used = template_draft(c, p, brief, evidence)
            text = _safe_polish(text, used, llm) or text
            specs.append(TaskSpec(f"{ak}|outreach|{person_key(p)}", ak, "outreach_draft",
                                  f"Draft outreach to {p.name} ({p.current_title or 'title unknown'}) at {c.name}",
                                  "draft_unsent", text))
    return specs
