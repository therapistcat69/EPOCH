from app.prompts.common import SYSTEM_RULES, evidence_block

SCHEMA = """{
  "summary": "string",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "hook_analysis": {"observation": "", "interpretation": "", "recommendation": ""},
  "pacing_analysis": {"observation": "", "interpretation": "", "recommendation": ""},
  "repetition_analysis": {"observation": "", "interpretation": "", "recommendation": ""},
  "title_alignment": {"observation": "", "interpretation": "", "recommendation": ""},
  "recommendations": [
    {"type": "cut|tighten|move|test|add|rewrite|other", "start": number|null, "end": number|null,
     "reason": "string", "evidence": "string citing the evidence", "confidence": number between 0 and 1}
  ]
}"""


def build_video_report_prompt(evidence: dict) -> tuple[str, str]:
    user = (
        "Write a VIDEO report using only this evidence package: metadata, YouTube Analytics, observed audience "
        "retention (audienceWatchRatio) with observed drop-offs linked to what was being said, and deterministic "
        "transcript features (hook latency, promise gap, pacing, repetition, CTAs). "
        "Timestamps are in seconds and must come from the evidence. Do NOT state expected retention improvements. "
        "'confidence' is your own judgement of how well the evidence supports the suggestion.\n\n"
        f"EVIDENCE:\n{evidence_block(evidence)}\n\nReturn JSON with this shape:\n{SCHEMA}"
    )
    return SYSTEM_RULES, user
