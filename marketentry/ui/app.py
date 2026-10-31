"""MarketEntryOS: Request | Live Execution Trace | Market Intelligence | Deliverables & CRM.
Run: streamlit run marketentry/ui/app.py"""
from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import streamlit as st

from marketentry.config import get_settings
from marketentry.orchestrator import Mission
from marketentry.ui.helpers import (accounts_rows, breakdown_rows, buyer_rows, competitor_rows, crm_view, evidence_rows,
                                    source_excerpt, tool_run_rows)

st.set_page_config(page_title="MarketEntryOS", layout="wide")

EXAMPLES = {
    "UK fintech compliance (spec example)": (
        "We sell cybersecurity compliance software for financial technology companies. Evaluate entry into the UK fintech "
        "market. Focus on companies with 50–500 employees. Estimate the addressable company universe using a £12,000 annual "
        "contract value assumption; identify competitors and buyer roles; buyers: CISO / Head of Compliance / CTO."),
    "Germany logistics (unseen)": (
        "We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, "
        "100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO."),
    "India healthcare": (
        "We sell patient-scheduling software to healthcare providers. Evaluate entry into India, 50–300 employees, "
        "₹400,000 annual contract value, buyers: CEO / COO."),
}
S = get_settings()


def df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def latest_saved() -> Path | None:
    files = sorted(Path(S.out_dir).glob("*/mission.pkl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


# ---- sidebar ---------------------------------------------------------------------------------
with st.sidebar:
    st.title("MarketEntryOS")
    st.caption("Autonomous market-entry engagement. LLM parses/writes prose only; facts, scores and CRM writes are Python.")
    replay = st.toggle("REPLAY (offline, from fixtures/raw)", value=S.replay)
    simulate = st.toggle("Simulate one transient API failure", value=S.simulate_transient_failure)
    use_llm = st.toggle("Use free LLM (Groq) for parsing/drafts", value=bool(S.llm_key()), disabled=not S.llm_key())
    max_enrich = st.number_input("Max company enrichments", 1, 25, S.max_company_enrichments)
    credit_cap = st.number_input("Credit cap per mission", 10.0, 2000.0, float(S.max_credits_per_mission))
    st.caption(f"Crustdata key: {'set' if S.api_key() else 'MISSING'} · LLM key: {'set' if S.llm_key() else 'not set (rules fallback)'}")
    if st.button("Load last saved run") and (p := latest_saved()):
        st.session_state["data"] = pickle.loads(p.read_bytes())
        st.session_state["loaded"] = str(p)

tab_req, tab_trace, tab_intel, tab_out = st.tabs(["1 Request", "2 Live execution trace", "3 Market intelligence", "4 Deliverables & CRM"])

with tab_req:
    ex = st.selectbox("Example requests", list(EXAMPLES))
    prompt = st.text_area("Client request", EXAMPLES[ex], height=150, key=f"prompt_{ex}")
    run = st.button("Run mission", type="primary")

with tab_trace:
    live = st.empty()

if run:
    s = S.model_copy(update={"replay": replay, "simulate_transient_failure": simulate, "llm_disabled": not use_llm,
                             "max_company_enrichments": int(max_enrich), "max_credits_per_mission": float(credit_cap)})
    lines: list[str] = []

    def on_event(e: dict) -> None:
        lines.append(f"{e['ts'][11:19]}  [{e['step']}] {e['msg']}" + (f"  (credits {e['credit']})" if e.get("credit") is not None else ""))
        live.code("\n".join(lines[-40:]), language="text")

    with st.spinner("Running mission end to end (no further input needed)…"):
        data = Mission(prompt, settings=s, on_event=on_event).run()
    st.session_state["data"], st.session_state["loaded"] = data, None
    if data.mission_id:
        try:
            (Path(s.out_dir) / data.mission_id).mkdir(parents=True, exist_ok=True)
            (Path(s.out_dir) / data.mission_id / "mission.pkl").write_bytes(pickle.dumps(data))
        except Exception:
            pass

d = st.session_state.get("data")
if d is None:
    with tab_trace:
        st.info("Run a mission from the Request tab (or load the last saved run in the sidebar).")
    st.stop()

# ---- trace -----------------------------------------------------------------------------------
with tab_trace:
    if st.session_state.get("loaded"):
        st.caption(f"Showing saved run {st.session_state['loaded']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("State", d.state)
    c2.metric("Credits used", d.credit_used if d.credit_used is not None else "unknown")
    c3.metric("Tool calls", len(d.tool_runs))
    c4.metric("Supported claims", f"{d.verified_claim_fraction:.0%}" if d.verified_claim_fraction is not None else "unknown")
    st.subheader("Steps")
    st.dataframe(df([{"step": s_.name, "status": s_.status, "note": s_.warning or ""} for s_ in d.steps]), hide_index=True, use_container_width=True)
    st.subheader("Actual Crustdata calls")
    st.dataframe(df(tool_run_rows(d)), hide_index=True, use_container_width=True)
    if d.llm_runs:
        st.subheader("LLM calls (parsing / draft wording only)")
        st.dataframe(df(d.llm_runs), hide_index=True, use_container_width=True)
    if d.warnings:
        st.subheader("Warnings")
        for w in d.warnings:
            st.warning(w)

# ---- intelligence ----------------------------------------------------------------------------
with tab_intel:
    b = d.brief
    if b is None:
        st.error("No brief could be produced.")
        st.stop()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Indexed companies (observed)", f"{d.universe.total_count:,}" if d.universe.total_count is not None else "unknown")
    m2.metric("Candidates fetched", d.universe.fetched)
    m3.metric("Competitors", len(d.competitors))
    m4.metric("Verified buyers", sum(len(v) for v in d.people.values()))
    st.subheader("Bottom-up market sizing")
    st.code(d.sizing.formula_text or "n/a", language="text")
    for cv in d.sizing.caveats:
        st.caption("• " + cv)
    with st.expander("Exact search filters, coverage and post-filters"):
        st.json(d.universe.filters_applied)
        st.write(d.universe.coverage_note)
        st.write(d.universe.post_filters or "no post-filters applied")
    st.subheader("Ranked target accounts")
    st.dataframe(df(accounts_rows(d)), hide_index=True, use_container_width=True)
    sl = d.companies[: b.max_target_accounts]
    if sl:
        pick = st.selectbox("Score breakdown & audit drill-down for", [c.name for c in sl])
        c = next(x for x in sl if x.name == pick)
        left, right = st.columns(2)
        with left:
            st.caption(f"fit {c.fit_score if c.fit_score is not None else 'unknown'} over assessable points · coverage {c.data_coverage:.0%} · {c.confidence} confidence")
            st.dataframe(df(breakdown_rows(c)), hide_index=True, use_container_width=True)
            st.write(c.icp_reasons)
        with right:
            ev_rows = evidence_rows(d, c.company_id or c.name)
            st.dataframe(df(ev_rows), hide_index=True, use_container_width=True)
        if ev_rows:
            chosen = st.selectbox("Open evidence record", [r["id"] for r in ev_rows])
            ev = next(e for e in d.evidence if e.evidence_id == chosen)
            st.json(source_excerpt(ev))
            if ev.status != "supported":
                st.warning(f"Verifier status: {ev.status}")
        unk = [f[8:] for f in c.flags if f.startswith("unknown:")]
        if unk:
            st.info(f"Honest unknowns for {c.name}: {', '.join(unk)} (no observed evidence; scored as unknown, not zero)")
    st.subheader("Buyer map")
    st.dataframe(df(buyer_rows(d)), hide_index=True, use_container_width=True)
    st.subheader("Competitive landscape")
    st.dataframe(df(competitor_rows(d)), hide_index=True, use_container_width=True)
    st.subheader("Assumption ledger")
    st.dataframe(df([a.model_dump() for a in b.assumptions]).astype(str), hide_index=True, use_container_width=True)
    if b.unsupported_constraints:
        st.error("Unsupported constraints: " + "; ".join(b.unsupported_constraints))

# ---- deliverables & CRM ----------------------------------------------------------------------
with tab_out:
    st.subheader("Downloadable deliverables")
    cols = st.columns(3)
    for i, (name, path) in enumerate(sorted(d.artifacts.items())):
        p = Path(path)
        if p.exists():
            cols[i % 3].download_button(f"⬇ {name}", p.read_bytes(), file_name=p.name, key=f"dl_{name}")
    if "Market_Entry_Report.html" in d.artifacts and Path(d.artifacts["Market_Entry_Report.html"]).exists():
        with st.expander("Preview report (HTML)"):
            st.components.v1.html(Path(d.artifacts["Market_Entry_Report.html"]).read_text(), height=700, scrolling=True)
    st.subheader("Local CRM (SQLite): rows written by this mission")
    if d.crm_db_path and Path(d.crm_db_path).exists():
        st.caption(f"{d.crm_db_path} · counts: {d.crm_counts}")
        view = crm_view(d.crm_db_path, d.mission_id)
        t1, t2, t3, t4 = st.tabs(["Companies", "People", "Tasks & unsent drafts", "Segments"])
        t1.dataframe(df(view["companies"]), hide_index=True, use_container_width=True)
        t2.dataframe(df(view["people"]), hide_index=True, use_container_width=True)
        t3.dataframe(df(view["crm_tasks"]), hide_index=True, use_container_width=True)
        t4.dataframe(df(view["segments"]), hide_index=True, use_container_width=True)
        drafts = [t for t in view["crm_tasks"] if t["status"] == "draft_unsent"]
        if drafts:
            with st.expander(f"{len(drafts)} outreach drafts (UNSENT, stored locally only)"):
                for t in drafts:
                    st.markdown(f"**{t['title']}**")
                    st.text(t["draft_text"])
    else:
        st.info("No CRM rows were written for this run.")
