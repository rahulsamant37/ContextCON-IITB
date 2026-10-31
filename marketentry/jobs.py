"""Background mission runner with a replayable event stream (for Server-Sent Events)."""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Iterator

from .brief_parser import parse_brief
from .config import Settings
from .contracts import MarketBrief
from .crm import mission_id_for
from .crustdata_client import CrustdataClient
from .evidence import utcnow
from .llm import LLMClient
from .orchestrator import Mission
from .serialize import save_mission

ALLOWED_CAPS = {"max_company_enrichments": (1, 25), "max_credits_per_mission": (10.0, 1000.0),
                "max_company_search_results": (10, 100), "max_buyer_searches": (1, 30)}


@dataclass
class Job:
    mission_id: str
    prompt: str
    owner: str | None = None
    status: str = "queued"  # queued | running | done | failed
    state: str | None = None  # engine state once finished (completed / completed_with_warnings / partial / failed)
    error: str | None = None
    created_at: str = field(default_factory=utcnow)
    events: list[dict] = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)


def clamp_caps(caps: dict | None) -> dict:
    out = {}
    for k, v in (caps or {}).items():
        if k in ALLOWED_CAPS and isinstance(v, (int, float)) and not isinstance(v, bool):
            lo, hi = ALLOWED_CAPS[k]
            out[k] = type(lo)(min(max(v, lo), hi))
    return out


class JobManager:
    def __init__(self, settings: Settings, *, max_workers: int = 2,
                 client_factory: Callable[[Settings], CrustdataClient] | None = None):
        self.settings = settings
        self.client_factory = client_factory
        self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mission")
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def run_settings(self, *, replay: bool, simulate: bool, use_llm: bool, caps: dict | None) -> Settings:
        return self.settings.model_copy(update={
            "replay": replay or self.settings.replay, "simulate_transient_failure": simulate,
            "llm_disabled": self.settings.llm_disabled or not use_llm, **clamp_caps(caps)})

    def parse(self, prompt: str, s: Settings, overrides: dict | None) -> tuple[MarketBrief, LLMClient]:
        llm = LLMClient(s)
        return parse_brief(prompt, llm, overrides), llm

    def submit(self, prompt: str, *, overrides: dict | None = None, replay: bool = False, simulate: bool = False,
               use_llm: bool = True, caps: dict | None = None, owner: str | None = None) -> Job:
        s = self.run_settings(replay=replay, simulate=simulate, use_llm=use_llm, caps=caps)
        brief, llm = self.parse(prompt, s, overrides)
        mid = mission_id_for(brief, owner)
        with self.lock:
            existing = self.jobs.get(mid)
            if existing and existing.status in ("queued", "running"):
                return existing  # same brief already in flight: attach instead of paying twice
            job = Job(mission_id=mid, prompt=prompt, owner=owner)
            self.jobs[mid] = job
        self.pool.submit(self._run, job, s, brief, llm)
        return job

    def _emit(self, job: Job, ev: dict) -> None:
        with job.cond:
            job.events.append({"seq": len(job.events), **ev})
            job.cond.notify_all()

    def _run(self, job: Job, s: Settings, brief: MarketBrief, llm: LLMClient) -> None:
        job.status = "running"
        self._emit(job, {"type": "status", "status": "running", "ts": utcnow()})
        try:
            client = self.client_factory(s) if self.client_factory else None
            m = Mission(job.prompt, settings=s, client=client, llm=llm, brief=brief, owner=job.owner,
                        on_event=lambda e: self._emit(job, {"type": "event", **e}))
            d = m.run()
            job.state = d.state
            self._emit(job, {"type": "status", "status": "done", "state": d.state, "ts": utcnow()})
            save_mission(d, s.out_dir, events=list(job.events))
            job.status = "done"
        except Exception as e:  # engine bugs surface as a failed job, never a hung stream
            job.status, job.error = "failed", f"{type(e).__name__}: {e}"
            self._emit(job, {"type": "status", "status": "failed", "error": job.error, "ts": utcnow()})
        finally:
            self._emit(job, {"type": "end"})

    def get(self, mission_id: str) -> Job | None:
        return self.jobs.get(mission_id)

    def stream(self, job: Job, start: int = 0, heartbeat_s: float = 15.0) -> Iterator[dict | None]:
        """Yields events from `start`; yields None as a heartbeat; returns after the terminal 'end' event."""
        i = start
        while True:
            with job.cond:
                while i >= len(job.events):
                    if not job.cond.wait(timeout=heartbeat_s):
                        break
                batch = job.events[i:]
            if not batch:
                yield None
                continue
            for ev in batch:
                i += 1
                yield ev
                if ev.get("type") == "end":
                    return
