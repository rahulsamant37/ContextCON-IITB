"""NL prompt -> MarketBrief. Rules always run. The LLM (if available) may only fill TEXT fields the rules could not
find; numeric fields (headcount range, ACV, currency) come from the prompt text via rules and are never LLM-invented."""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from .contracts import Assumption, MarketBrief
from .llm import LLMClient

COUNTRY_ALIASES: dict[str, str] = {
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom",
    "great britain": "United Kingdom", "england": "United Kingdom",
    "united states": "United States", "usa": "United States", "u.s.": "United States", "us": "United States",
    "india": "India", "germany": "Germany", "france": "France", "singapore": "Singapore", "canada": "Canada",
    "australia": "Australia", "netherlands": "Netherlands", "ireland": "Ireland", "spain": "Spain",
    "brazil": "Brazil", "japan": "Japan", "sweden": "Sweden", "switzerland": "Switzerland",
    "united arab emirates": "United Arab Emirates", "uae": "United Arab Emirates",
}
# keyword in prompt -> search phrase used for (free) autocomplete resolution of Crustdata taxonomy values
SECTOR_KEYWORDS: list[tuple[str, str]] = [
    ("financial technology", "FinTech"), ("fintech", "FinTech"), ("insurtech", "InsurTech"),
    ("insurance", "Insurance"), ("logistics", "Logistics"), ("freight", "Logistics"),
    ("supply chain", "Supply Chain Management"), ("e-commerce", "E-Commerce"), ("ecommerce", "E-Commerce"),
    ("healthtech", "Healthcare"), ("healthcare", "Healthcare"), ("health care", "Healthcare"),
    ("edtech", "EdTech"), ("cybersecurity", "Cybersecurity"), ("saas", "SaaS"), ("manufacturing", "Manufacturing"),
    ("real estate", "Real Estate"), ("retail", "Retail"), ("telecom", "Telecommunications"),
]
CURRENCIES = {"£": "GBP", "€": "EUR", "$": "USD", "₹": "INR", "gbp": "GBP", "eur": "EUR", "usd": "USD", "inr": "INR",
              "rs.": "INR", "rs": "INR"}
DEFAULT_ROLES = ["CEO", "COO", "CTO"]
_NUM = r"\d[\d,]*(?:\.\d+)?"
_ROLE_RE = re.compile(
    r"\b(Head of [A-Z][\w&]*(?: (?:and )?[A-Z][\w&]*)?|VP(?: of)? [A-Z][\w&]*(?: [A-Z][\w&]*)?|"
    r"Vice President(?: of)? [A-Z][\w&]*|Director of [A-Z][\w&]*(?: [A-Z][\w&]*)?|"
    r"Chief [A-Z][\w]*(?: [A-Z][\w]*)? Officer|C(?:EO|TO|FO|OO|IO|ISO|RO|MO)\b)")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _scaled(n: str, suffix: str | None) -> float:
    v = _num(n)
    return v * {"k": 1_000, "m": 1_000_000}.get((suffix or "").lower(), 1)


def parse_employees(t: str) -> tuple[int | None, int | None]:
    m = re.search(rf"({_NUM})\s*(?:-|–|—|to|and)\s*({_NUM})\s*(?:\+\s*)?(?:full[- ]time\s+)?(?:employees|staff|people|headcount)", t, re.I) \
        or re.search(rf"(?:employees|headcount|size)[^.\d]{{0,25}}?(?:between\s+)?({_NUM})\s*(?:-|–|—|to|and)\s*({_NUM})", t, re.I)
    if m:
        a, b = int(_num(m.group(1))), int(_num(m.group(2)))
        return (a, b) if a <= b else (None, None)  # inverted range => unknown, flagged by caller
    lo = re.search(rf"(?:more than|over|at least|minimum of)\s+({_NUM})\s*(?:employees|staff|people)", t, re.I)
    hi = re.search(rf"(?:fewer than|under|less than|at most|up to)\s+({_NUM})\s*(?:employees|staff|people)", t, re.I)
    return (int(_num(lo.group(1))) if lo else None, int(_num(hi.group(1))) if hi else None)


def parse_acv(t: str) -> tuple[float | None, str | None]:
    cur_re = r"(£|€|\$|₹|\bRs\.?|\bGBP|\bEUR|\bUSD|\bINR)"
    m = re.search(rf"{cur_re}\s?({_NUM})\s*(k|m)?\b", t, re.I) \
        or None
    if m:
        return _scaled(m.group(2), m.group(3)), CURRENCIES.get(m.group(1).lower())
    m = re.search(rf"({_NUM})\s*(k|m)?\s*(GBP|EUR|USD|INR)\b", t, re.I)
    if m:
        return _scaled(m.group(1), m.group(2)), CURRENCIES.get(m.group(3).lower())
    return None, None


def parse_country(t: str) -> str | None:
    low = t.lower()
    hits = []
    for alias, canon in COUNTRY_ALIASES.items():
        for m in re.finditer(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", low):
            # "us"/"in" style ambiguity: only accept "us" when capitalised US/U.S. in the original text
            if alias == "us" and not re.search(r"\bUS\b", t):
                continue
            hits.append((m.start(), canon))
    if not hits:
        return None
    pref = re.search(r"(?:entry|enter|entering|expand\w*|launch\w*|into|in the|in)\s+(?:the\s+)?([A-Za-z.\s]{2,30})", t)
    if pref:
        seg = pref.group(1).lower()
        for alias, canon in sorted(COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
            if seg.strip().startswith(alias):
                return canon
    return min(hits)[1]


def parse_sector(t: str, product_desc: str | None = None) -> str | None:
    """Target sector. The product description span is removed first so 'cybersecurity compliance software for
    fintech' yields FinTech, not Cybersecurity."""
    if product_desc:
        t = t.replace(product_desc, " ")
    low = t.lower()
    found = [(low.find(k), v) for k, v in SECTOR_KEYWORDS if k in low]
    if found:
        return min(found)[1]
    m = re.search(r"\bfor\s+([a-z][a-z &/-]{3,40}?)\s+(?:companies|firms|businesses|startups|enterprises|organisations|organizations)", low)
    return m.group(1).strip().title() if m else None


def parse_description(t: str) -> str | None:
    m = re.search(r"\b(?:we\s+(?:sell|offer|build|provide|make)|our product is)\s+(.+?)(?:\s+(?:for|to)\s+|[.,;]|$)", t, re.I)
    return m.group(1).strip() if m else None


def parse_roles(t: str) -> list[str]:
    seg = re.search(r"buyer(?: roles| personas)?\s*(?:are|:|include|=)?\s*(.+?)(?:\.|;|$)", t, re.I)
    scope = seg.group(1) if seg else t
    roles = [r.strip() for r in _ROLE_RE.findall(scope)]
    if not roles and seg:  # free-text list: "Head of Fleet / VP Operations, CTO"
        roles = [p.strip() for p in re.split(r"\s*(?:/|,|\bor\b|\band\b)\s*", seg.group(1)) if 2 < len(p.strip()) < 40]
    return list(dict.fromkeys(roles))


def parse_caps(t: str) -> dict[str, int]:
    out: dict[str, int] = {}
    m = re.search(r"(?:top|shortlist of|ranked shortlist of|up to)\s+(\d{1,3})\s+(?:target\s+)?(?:accounts|companies)", t, re.I)
    if m:
        out["max_target_accounts"] = int(m.group(1))
    return out


def rules_parse(prompt: str) -> dict[str, Any]:
    lo, hi = parse_employees(prompt)
    acv, cur = parse_acv(prompt)
    desc = parse_description(prompt)
    return {"target_country": parse_country(prompt), "target_industry": parse_sector(prompt, desc),
            "product_description": desc, "target_buyer_roles": parse_roles(prompt),
            "employee_min": lo, "employee_max": hi, "annual_contract_value": acv, "currency": cur, **parse_caps(prompt)}


_LLM_SYSTEM = (
    "Extract fields from a B2B market-entry request. Reply with a JSON object with keys: product_name (string or null), "
    "product_description (short noun phrase or null), target_country (full English country name or null), "
    "target_industry (short sector name or null), target_buyer_roles (list of job titles stated in the text; [] if none), "
    "competitor_keywords (2-4 short search phrases describing the product category). "
    "Use ONLY information present in the text. Use null / [] when not stated. Do not output numbers."
)


def _llm_fields(prompt: str, llm: LLMClient) -> dict[str, Any]:
    out = llm.complete_json(_LLM_SYSTEM, prompt, purpose="brief_parse")
    if not out:
        return {}
    clean: dict[str, Any] = {}
    for k in ("product_name", "product_description", "target_industry"):
        if isinstance(out.get(k), str) and out[k].strip():
            clean[k] = out[k].strip()[:120]
    c = out.get("target_country")
    if isinstance(c, str) and COUNTRY_ALIASES.get(c.strip().lower()):
        clean["target_country"] = COUNTRY_ALIASES[c.strip().lower()]
    for k in ("target_buyer_roles", "competitor_keywords"):
        v = out.get(k)
        if isinstance(v, list):
            clean[k] = [x.strip()[:60] for x in v if isinstance(x, str) and x.strip()][:6]
    return clean


def parse_brief(prompt: str, llm: LLMClient | None = None, overrides: dict[str, Any] | None = None) -> MarketBrief:
    """Always returns a MarketBrief. Anything unknown is None/'unknown' with an Assumption entry; nothing is invented."""
    r = rules_parse(prompt)
    ll = _llm_fields(prompt, llm) if llm is not None and llm.available else {}
    A: list[Assumption] = []
    unsupported: list[str] = []
    f: dict[str, Any] = {}

    def pick(field: str, default: Any, note: str, text_ok_from_llm: bool = True) -> Any:
        if r.get(field):
            A.append(Assumption(field=field, value=r[field], source="user", note="parsed from request text"))
            return r[field]
        if text_ok_from_llm and ll.get(field):
            A.append(Assumption(field=field, value=ll[field], source="inferred", note="LLM extraction from request text"))
            return ll[field]
        A.append(Assumption(field=field, value=default, source="defaulted", note=note))
        return default

    f["target_country"] = pick("target_country", "unknown", "country not recognised in request")
    if f["target_country"] == "unknown":
        unsupported.append("target_country not recognised; discovery cannot run")
    f["target_industry"] = pick("target_industry", "unknown", "sector not recognised in request")
    if f["target_industry"] == "unknown":
        unsupported.append("target_industry not recognised; discovery cannot run")
    f["product_description"] = pick("product_description", "unspecified product", "no product description found")
    roles = r["target_buyer_roles"] or ll.get("target_buyer_roles") or []
    if roles:
        A.append(Assumption(field="target_buyer_roles", value=roles, source="user" if r["target_buyer_roles"] else "inferred",
                            note="from request text"))
    else:
        roles = DEFAULT_ROLES
        A.append(Assumption(field="target_buyer_roles", value=roles, source="defaulted",
                            note="no buyer roles stated; generic executive roles assumed"))
    f["target_buyer_roles"] = roles
    f["product_name"] = ll.get("product_name") or "Unnamed product"
    f["competitor_keywords"] = ll.get("competitor_keywords") or [f["product_description"]]
    A.append(Assumption(field="competitor_keywords", value=f["competitor_keywords"],
                        source="inferred" if ll.get("competitor_keywords") else "defaulted",
                        note="derived from product description"))

    # numeric facts: rules only
    lo, hi = r["employee_min"], r["employee_max"]
    if lo is None and hi is None and re.search(r"employees|headcount", prompt, re.I) and re.search(rf"{_NUM}\s*(?:-|–|—|to)\s*{_NUM}", prompt):
        unsupported.append("employee range in request looked inverted or unparseable; ignored")
    f["employee_min"], f["employee_max"] = lo, hi
    for fld, v in (("employee_min", lo), ("employee_max", hi)):
        A.append(Assumption(field=fld, value=v, source="user" if v is not None else "defaulted",
                            note="parsed from request text" if v is not None else "no bound stated; not filtered"))
    acv, cur = r["annual_contract_value"], r["currency"]
    f["annual_contract_value"], f["currency"] = acv, cur
    A.append(Assumption(field="annual_contract_value", value=acv, source="user" if acv is not None else "defaulted",
                        note="client-supplied" if acv is not None else "no ACV supplied; monetary estimates omitted"))
    if acv is not None and cur is None:
        unsupported.append("ACV given without a recognisable currency")
    if r.get("max_target_accounts"):
        f["max_target_accounts"] = r["max_target_accounts"]

    for k, v in (overrides or {}).items():  # structured UI settings win and are labelled as user input
        if k in MarketBrief.model_fields and v is not None:
            f[k] = v
            A.append(Assumption(field=k, value=v, source="user", note="structured override"))

    try:
        return MarketBrief(raw_prompt=prompt, assumptions=A, unsupported_constraints=unsupported, **f)
    except ValidationError as e:  # e.g. inverted override range; keep going with the range dropped
        f["employee_min"] = f["employee_max"] = None
        unsupported.append(f"invalid structured settings dropped: {e.errors()[0]['msg']}")
        return MarketBrief(raw_prompt=prompt, assumptions=A, unsupported_constraints=unsupported, **f)
