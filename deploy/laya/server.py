"""Self-hosted Laya decision server with a Jev-compatible API.

    POST /v1/systemone   {"state": <text|object|array>, "questions": {...}}
    ->  {"model": "...", "answers": {name: {...}}, "usage": {...}}

Questions use the same three primitives as TypeSafe's Jev — choice, score,
noul — so the CareerCraft backend talks to either one through
app/services/decision_engine.py (set LAYA_URL, leave TYPESAFE_API_KEY empty).

Laya (https://laya.convaiinnovations.com, Apache-2.0) runs bidirectional
encoders locally; Router picks the English or multilingual checkpoint from
the text's script. Its authors report weak zero-shot accuracy on some
decision benchmarks and recommend fine-tuning, and choice questions degrade
past ~20 options — CareerCraft only acts on answers above
DECISION_ENGINE_MIN_CONFIDENCE and asks the user otherwise.
"""

from __future__ import annotations

import hmac
import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

API_KEY = os.environ.get("LAYA_API_KEY", "")
MAX_QUESTIONS = 16

app = FastAPI(title="Laya decision server")
_router = None


def router():
    global _router
    if _router is None:
        from laya import Router

        _router = Router(
            preload=os.environ.get("LAYA_PRELOAD", "true").lower() == "true"
        )
    return _router


class SystemOneRequest(BaseModel):
    state: Any
    questions: dict[str, dict[str, Any]]
    model: str | None = None


def _normalize(name: str, question: dict, raw: dict) -> dict:
    """Shape one Laya answer like Jev's, keeping whatever extra keys Laya returns."""
    kind = question["type"]
    answer = {"type": kind, **(raw or {})}
    if kind == "noul":
        answer["noul"] = float(answer.get("noul", answer.get("probability", 0.5)))
    elif kind == "score":
        answer.setdefault("confidence", 0.0)
    elif kind == "choice":
        answer.setdefault(
            "confidence", max((answer.get("probabilities") or {0: 0.0}).values())
        )
    return answer


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "loaded": _router is not None}


@app.post("/v1/systemone")
def systemone(body: SystemOneRequest, authorization: str = Header(default="")) -> dict:
    if API_KEY and not hmac.compare_digest(authorization, f"Bearer {API_KEY}"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not body.questions or len(body.questions) > MAX_QUESTIONS:
        raise HTTPException(
            status_code=422, detail=f"1-{MAX_QUESTIONS} questions required"
        )
    for name, question in body.questions.items():
        if question.get("type") not in {"choice", "score", "noul"}:
            raise HTTPException(
                status_code=422, detail=f"{name}: unsupported question type"
            )

    started = time.perf_counter()
    kwargs = {"model": body.model} if body.model else {}
    result = router().predict(body.state, body.questions, **kwargs)
    raw_answers = result.get("answers", {}) if isinstance(result, dict) else {}
    answers = {
        name: _normalize(name, question, raw_answers.get(name, {}))
        for name, question in body.questions.items()
    }
    return {
        "model": (
            (result.get("routing") or {}).get("model", "laya")
            if isinstance(result, dict)
            else "laya"
        ),
        "answers": answers,
        "usage": {"latency_ms": round((time.perf_counter() - started) * 1000, 1)},
    }
