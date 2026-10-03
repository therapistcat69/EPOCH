"""Groq explanation layer for ML predictions. The model is the source of truth; Groq only narrates.

Guard rails: only explanations whose (start, end) match a model-supplied risk region are kept, so the LLM cannot
introduce new timestamps; numbers are never taken from the LLM output.
"""
import logging

from app.errors import AppError
from app.prompts.ml_explanation_prompt import build_ml_explanation_prompt
from app.schemas.reports import GroqMLExplanation
from app.services.groq_service import GroqService

logger = logging.getLogger("retention.ml_explain")


def _snippet(segments: list[dict], start: float, end: float, limit: int = 3) -> list[str]:
    out = []
    for s in segments:
        s0 = float(s.get("start", s.get("start_time", s.get("start_seconds", 0))))
        s1 = float(s.get("end", s.get("end_time", s.get("end_seconds", 0))))
        if s1 >= start and s0 <= end:
            out.append(str(s.get("text", ""))[:220])
        if len(out) >= limit:
            break
    return out


def build_evidence(prediction: dict, segments: list[dict], title: str) -> dict:
    pts = prediction["points"]
    step = max(1, len(pts) // 12)
    return {
        "video_title": title,
        "trained_on": prediction["trained_on"], "model": f"{prediction['model_name']} {prediction['model_version']}",
        "duration_seconds": prediction["duration_seconds"],
        "predicted_retention_samples": [{"t": round(p["start_seconds"]), "retention_pct": round(p["predicted_retention"], 1)} for p in pts[::step]],
        "risk_regions": [
            {"start_seconds": r["start_seconds"], "end_seconds": r["end_seconds"], "risk_score": round(r["risk_score"], 2),
             "predicted_drop_points": round(r["predicted_drop"], 1), "model_attributed_features": [f["label"] for f in r["factors"]],
             "transcript": _snippet(segments, r["start_seconds"], r["end_seconds"])}
            for r in prediction["risk_segments"]
        ],
        "uncertainty": "available" if prediction["uncertainty"]["available"] else "unavailable",
    }


async def explain(groq: GroqService, prediction: dict, segments: list[dict], title: str = "") -> dict:
    if not groq.configured:
        return {"available": False, "reason": "GROQ_NOT_CONFIGURED", "message": "AI explanation unavailable: GROQ_API_KEY is not set on the server."}
    if not prediction["risk_segments"]:
        return {"available": False, "reason": "NO_RISK_REGIONS", "message": "The model found no elevated-risk regions to explain."}
    evidence = build_evidence(prediction, segments, title)
    system, user = build_ml_explanation_prompt(evidence)
    try:
        res = await groq.chat_json(system, user, GroqMLExplanation, max_tokens=2500)
    except AppError as exc:
        return {"available": False, "reason": exc.code, "message": exc.message}
    allowed = {(round(r["start_seconds"], 1), round(r["end_seconds"], 1)) for r in prediction["risk_segments"]}
    kept = [e for e in res.risk_explanations if (round(e.start_seconds, 1), round(e.end_seconds, 1)) in allowed]
    return {"available": True, "report": {"summary": res.summary, "risk_explanations": [e.model_dump() for e in kept]},
            "note": "Written by Groq from the model's output; numbers and timestamps are the model's."}
