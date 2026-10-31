"""FastAPI backend for the web app. Thin: all logic lives in the engine modules.
No sign-in: each browser gets an automatic guest account through an HttpOnly session cookie (SameSite=Lax).
Every research endpoint is scoped to its owner."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .auth import AuthStore, User
from .brief_parser import COUNTRY_ALIASES
from .config import Settings, get_settings
from .contracts import CompanyRecord, Evidence
from .crm import CRM, mission_id_for
from .crustdata_client import CrustdataClient
from .jobs import JobManager
from .presenters import breakdown_rows, source_excerpt
from .serialize import list_summaries, load_json, valid_mission_id

MAX_PROMPT = 4000
COOKIE = "me_session"


class PreviewIn(BaseModel):
    prompt: str = Field(min_length=10, max_length=MAX_PROMPT)
    use_llm: bool = True


class MissionIn(BaseModel):
    prompt: str = Field(min_length=10, max_length=MAX_PROMPT)
    overrides: dict[str, Any] | None = None
    replay: bool = False
    simulate_failure: bool = False
    use_llm: bool = True
    caps: dict[str, float] | None = None


class StageIn(BaseModel):
    stage: str


class TaskIn(BaseModel):
    status: str | None = None
    draft_text: str | None = Field(default=None, max_length=5000)


def estimate_credits(s: Settings) -> dict[str, float]:
    """Cost preview from the measured live costs: ~0.53/search result, 2/enrichment, ~0.23/person, ~1.5 for competitors+web."""
    typical = 0.53 * s.max_company_search_results + 2 * s.max_company_enrichments + 4 + 2.5
    return {"typical": round(typical, 1), "cap": s.max_credits_per_mission}


def create_app(settings: Settings | None = None,
               client_factory: Callable[[Settings], CrustdataClient] | None = None) -> FastAPI:
    s = settings or get_settings()
    app = FastAPI(title="MarketEntry API", version="1.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    jobs = JobManager(s, client_factory=client_factory)
    out = Path(s.out_dir)
    auth = AuthStore(out / "app.db", s.session_days)
    app.state.jobs, app.state.settings, app.state.auth = jobs, s, auth

    # ---- guest sessions --------------------------------------------------------------------------
    GUEST_DAYS = 365

    def current_user(request: Request, response: Response) -> User:
        """The caller's account; a first-time visitor silently gets a guest account and a session cookie."""
        user = auth.user_for_token(request.cookies.get(COOKIE))
        if user is None:
            user = auth.create_guest()
            response.set_cookie(COOKIE, auth.create_session(user.id, GUEST_DAYS), httponly=True, samesite="lax",
                                secure=s.cookie_secure, max_age=GUEST_DAYS * 86400, path="/")
        return user

    @app.get("/api/auth/me")
    def me(user: User = Depends(current_user)) -> dict:
        return {"user": user.public()}

    # ---- ownership helpers -----------------------------------------------------------------------
    def owned_job(mid: str, user: User):
        job = jobs.get(mid)
        return job if job is not None and job.owner == user.id else None

    def mission_or_404(mid: str, user: User) -> dict:
        if not valid_mission_id(mid):
            raise HTTPException(404, "Research not found.")
        data = load_json(out, mid, "mission.json")
        if data is None or data.get("owner") != user.id:
            job = owned_job(mid, user)
            if job and job.status in ("queued", "running"):
                raise HTTPException(409, "Research still running.")
            raise HTTPException(404, "Research not found.")  # never reveal that another user's research exists
        return data

    # ---- public ----------------------------------------------------------------------------------
    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/options")
    def options() -> dict:
        """Choices for the guided form. Countries are the ones the engine can map reliably; sectors and roles are
        suggestions only (free text is accepted and mapped to Crustdata categories at run time)."""
        return {
            "countries": sorted(set(COUNTRY_ALIASES.values())),
            "currencies": ["USD", "EUR", "GBP", "INR", "SGD", "AUD", "CAD", "AED", "CHF", "SEK", "JPY", "BRL"],
            "sectors": ["FinTech", "InsurTech", "Logistics", "Supply Chain Management", "Healthcare", "E-Commerce",
                        "Cybersecurity", "SaaS", "EdTech", "Manufacturing", "Real Estate", "Retail", "Telecommunications"],
            "roles": ["CEO", "CTO", "COO", "CFO", "CISO", "Head of Operations", "Head of Compliance", "VP Sales",
                      "VP Operations", "Head of Fleet", "Head of Procurement", "Head of Marketing"],
            "size_presets": [[1, 50], [50, 200], [200, 1000], [1000, None]],
        }

    # ---- signed-in -------------------------------------------------------------------------------
    @app.get("/api/settings")
    def get_public_settings(user: User = Depends(current_user)) -> dict:  # key presence only, never values
        return {"crustdata_key_set": bool(s.api_key()), "llm_key_set": bool(s.llm_key()), "llm_model": s.llm_model,
                "replay_default": s.replay, "caps": {"max_credits_per_mission": s.max_credits_per_mission,
                "max_company_enrichments": s.max_company_enrichments, "max_company_search_results": s.max_company_search_results,
                "max_buyer_searches": s.max_buyer_searches}, "estimate": estimate_credits(s)}

    @app.post("/api/briefs/preview")
    def preview(body: PreviewIn, user: User = Depends(current_user)) -> dict:
        run_s = jobs.run_settings(replay=False, simulate=False, use_llm=body.use_llm, caps=None)
        brief, llm = jobs.parse(body.prompt, run_s, None)
        return {"brief": brief.model_dump(mode="json"), "mission_id": mission_id_for(brief, user.id),
                "ready": brief.target_country != "unknown" and brief.target_industry != "unknown",
                "llm_used": any(r.get("ok") for r in llm.runs), "estimate": estimate_credits(run_s)}

    @app.post("/api/missions", status_code=202)
    def create_mission(body: MissionIn, user: User = Depends(current_user)) -> dict:
        if not body.replay and not s.replay and not s.api_key():
            raise HTTPException(400, "CRUSTDATA_API_KEY is not configured on the server (or enable demo mode)")
        job = jobs.submit(body.prompt, overrides=body.overrides, replay=body.replay, simulate=body.simulate_failure,
                          use_llm=body.use_llm, caps=body.caps, owner=user.id)
        return {"mission_id": job.mission_id, "status": job.status}

    @app.get("/api/missions")
    def list_missions(user: User = Depends(current_user)) -> dict:
        running = [{"mission_id": j.mission_id, "status": j.status, "prompt": j.prompt, "created_at": j.created_at}
                   for j in jobs.jobs.values() if j.owner == user.id and j.status in ("queued", "running")]
        return {"running": running, "missions": list_summaries(out, user.id)}

    @app.get("/api/missions/{mid}")
    def get_mission(mid: str, include: str = Query("core"), user: User = Depends(current_user)) -> dict:
        data = mission_or_404(mid, user)
        if include == "core":  # heavy lists have their own endpoints
            data = {k: v for k, v in data.items() if k not in ("evidence", "tool_runs")}
        return data

    @app.get("/api/missions/{mid}/status")
    def mission_status(mid: str, user: User = Depends(current_user)) -> dict:
        if not valid_mission_id(mid):
            raise HTTPException(404, "Research not found.")
        job = owned_job(mid, user)
        if job:
            return {"mission_id": mid, "status": job.status, "state": job.state, "error": job.error, "events": len(job.events),
                    "prompt": job.prompt}
        data = load_json(out, mid, "summary.json")
        if data is None or data.get("owner") != user.id:
            raise HTTPException(404, "Research not found.")
        return {"mission_id": mid, "status": "done", "state": data.get("state"), "error": None, "events": 0, "prompt": data.get("prompt")}

    @app.get("/api/missions/{mid}/events")
    def events(mid: str, start: int = 0, user: User = Depends(current_user)) -> StreamingResponse:
        if not valid_mission_id(mid):
            raise HTTPException(404, "Research not found.")
        job = owned_job(mid, user)
        if job is None:
            summ = load_json(out, mid, "summary.json")
            if summ is None or summ.get("owner") != user.id:
                raise HTTPException(404, "Research not found.")

        def gen():
            if job is not None:
                for ev in jobs.stream(job, start):
                    yield ": keepalive\n\n" if ev is None else f"id: {ev['seq']}\ndata: {json.dumps(ev, default=str)}\n\n"
                return
            for i, ev in enumerate(load_json(out, mid, "events.json") or []):
                if i >= start:
                    yield f"id: {ev.get('seq', i)}\ndata: {json.dumps(ev, default=str)}\n\n"
            yield 'data: {"type": "end"}\n\n'
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

    @app.get("/api/missions/{mid}/accounts/{company_id}")
    def account(mid: str, company_id: str, user: User = Depends(current_user)) -> dict:
        data = mission_or_404(mid, user)
        acc = next((a for a in data["accounts"] if a.get("company_id") == company_id), None)
        if acc is None:
            raise HTTPException(404, "Company not found.")
        rec = CompanyRecord(**{k: v for k, v in acc.items() if k != "rank"})
        return {"account": acc, "breakdown": breakdown_rows(rec),
                "evidence": [e for e in data["evidence"] if e["subject_id"] == company_id],
                "people": data["people"].get(company_id, [])}

    @app.get("/api/missions/{mid}/evidence")
    def evidence(mid: str, subject: str | None = None, status: str | None = None, q: str | None = None,
                 limit: int = Query(200, le=2000), offset: int = 0, user: User = Depends(current_user)) -> dict:
        items = mission_or_404(mid, user)["evidence"]
        if subject:
            items = [e for e in items if e["subject_id"] == subject]
        if status:
            items = [e for e in items if e["status"] == status]
        if q:
            ql = q.lower()
            items = [e for e in items if ql in e["claim"].lower() or ql in (e.get("field_path") or "").lower()]
        return {"total": len(items), "items": items[offset: offset + limit]}

    @app.get("/api/missions/{mid}/evidence/{evidence_id}/source")
    def evidence_source(mid: str, evidence_id: str, user: User = Depends(current_user)) -> dict:
        raw = next((e for e in mission_or_404(mid, user)["evidence"] if e["evidence_id"] == evidence_id), None)
        if raw is None:
            raise HTTPException(404, "Source not found.")
        ref = raw.get("raw_ref")
        if ref:  # only ever read files we recorded ourselves
            allowed = [out.resolve(), Path(s.fixtures_dir).resolve()]
            if not any(a == Path(ref).resolve() or a in Path(ref).resolve().parents for a in allowed):
                raise HTTPException(403, "Source outside recorded data directories.")
        return source_excerpt(Evidence(**raw))

    @app.get("/api/missions/{mid}/tool-runs")
    def tool_runs(mid: str, user: User = Depends(current_user)) -> list[dict]:
        return mission_or_404(mid, user)["tool_runs"]

    @app.get("/api/missions/{mid}/crm")
    def crm(mid: str, user: User = Depends(current_user)) -> dict:
        mission_or_404(mid, user)
        c = CRM(s.crm_path)
        try:
            comps = [{k: r[k] for k in ("id", "account_key", "crustdata_company_id", "name", "domain", "segment", "stage",
                                        "fit_score", "coverage_score", "verification_status")} for r in c.rows("companies", mid)]
            tasks = [{k: r[k] for k in ("id", "company_id", "task_type", "title", "status", "draft_text")} for r in c.rows("crm_tasks", mid)]
            people = [{k: r[k] for k in ("id", "company_id", "name", "title", "verified_employment")} for r in c.rows("people", mid)]
            return {"companies": comps, "tasks": tasks, "people": people, "stages": list(CRM.STAGES),
                    "task_statuses": list(CRM.TASK_STATUSES), "counts": c.counts(mid)}
        finally:
            c.close()

    @app.patch("/api/missions/{mid}/crm/companies/{company_row_id}")
    def set_stage(mid: str, company_row_id: int, body: StageIn, user: User = Depends(current_user)) -> dict:
        mission_or_404(mid, user)
        c = CRM(s.crm_path)
        try:
            try:
                ok = c.set_company_stage(mid, company_row_id, body.stage)
            except ValueError as e:
                raise HTTPException(422, str(e))
            if not ok:
                raise HTTPException(404, "Company not found.")
            return {"id": company_row_id, "stage": body.stage}
        finally:
            c.close()

    @app.patch("/api/missions/{mid}/crm/tasks/{task_id}")
    def patch_task(mid: str, task_id: int, body: TaskIn, user: User = Depends(current_user)) -> dict:
        mission_or_404(mid, user)
        c = CRM(s.crm_path)
        try:
            try:
                ok = c.update_task(mid, task_id, body.status, body.draft_text)
            except ValueError as e:
                raise HTTPException(422, str(e))
            if not ok:
                raise HTTPException(404, "Task not found.")
            return {"id": task_id, "status": body.status}
        finally:
            c.close()

    @app.get("/api/missions/{mid}/artifacts/{name}")
    def artifact(mid: str, name: str, user: User = Depends(current_user)) -> FileResponse:
        data = mission_or_404(mid, user)
        if name not in data["artifacts"] or name == "marketentry.db":  # allow-list; the shared CRM db is not downloadable
            raise HTTPException(404, "File not found.")
        p = out / mid / name
        if not p.is_file():
            raise HTTPException(404, "File missing.")
        return FileResponse(p, filename=name)

    @app.exception_handler(Exception)
    async def unhandled(_, exc: Exception) -> JSONResponse:  # never leak internals or paths
        return JSONResponse({"detail": "Something went wrong on our side."}, status_code=500)

    return app


app = create_app()
