"""Minimal OpenAI-compatible chat client (Groq free tier by default). Never raises: returns None on any
failure so callers fall back to rules/templates. The LLM only parses text and writes prose."""
from __future__ import annotations

import json
import time
from typing import Callable

import httpx

from .config import Settings, get_settings


class LLMClient:
    def __init__(self, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.s = settings or get_settings()
        self._http = httpx.Client(base_url=self.s.llm_base_url, timeout=self.s.llm_timeout_s, transport=transport)
        self._sleep = sleep
        self.runs: list[dict] = []  # shown in the execution trace; no prompts/keys stored

    @property
    def available(self) -> bool:
        return bool(self.s.llm_key()) and not self.s.llm_disabled

    def _chat(self, system: str, user: str, *, json_mode: bool, max_tokens: int, purpose: str) -> str | None:
        if not self.available:
            return None
        body: dict = {"model": self.s.llm_model, "temperature": 0, "max_tokens": max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if "gpt-oss" in self.s.llm_model:  # reasoning model: hidden reasoning tokens count against max_tokens
            body["reasoning_effort"] = "low"
        t0 = time.monotonic()
        err = None
        for attempt in (1, 2, 3):
            try:
                r = self._http.post("/chat/completions", json=body,
                                    headers={"Authorization": f"Bearer {self.s.llm_key()}"})
                if r.status_code == 200:
                    text = r.json()["choices"][0]["message"]["content"]
                    if not (text or "").strip():
                        err = "empty_response"
                        break
                    self.runs.append({"purpose": purpose, "model": self.s.llm_model, "ok": True, "attempt": attempt,
                                      "duration_ms": int((time.monotonic() - t0) * 1000)})
                    return text
                err = f"http_{r.status_code}"
                if r.status_code != 429 and r.status_code < 500:
                    break
            except (httpx.TransportError, KeyError, IndexError, ValueError) as e:
                err = type(e).__name__
            if attempt < 3:
                self._sleep(1.5 * attempt)
        self.runs.append({"purpose": purpose, "model": self.s.llm_model, "ok": False, "error_type": err,
                          "duration_ms": int((time.monotonic() - t0) * 1000)})
        return None

    def complete_json(self, system: str, user: str, *, purpose: str, max_tokens: int = 1200) -> dict | None:
        text = self._chat(system, user, json_mode=True, max_tokens=max_tokens, purpose=purpose)
        if text is None:
            return None
        try:
            out = json.loads(text)
            return out if isinstance(out, dict) else None
        except ValueError:
            self.runs[-1].update(ok=False, error_type="invalid_json")
            return None

    def complete_text(self, system: str, user: str, *, purpose: str, max_tokens: int = 1200) -> str | None:
        t = self._chat(system, user, json_mode=False, max_tokens=max_tokens, purpose=purpose)
        return t.strip() if t else None
