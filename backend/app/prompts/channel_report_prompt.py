from app.prompts.common import SYSTEM_RULES, evidence_block

SCHEMA = """{
  "summary": "string (2-4 sentences grounded in the evidence)",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "content_patterns": ["string"],
  "observed_performance_patterns": ["string (association wording only)"],
  "recommendations": [{"observation": "string", "interpretation": "string", "recommendation": "string"}],
  "experiments_to_try": ["string"]
}"""


def build_channel_report_prompt(evidence: dict) -> tuple[str, str]:
    user = (
        "Write a CHANNEL report for the creator using only this evidence package "
        "(aggregated YouTube Analytics statistics and deterministic content analysis).\n\n"
        f"EVIDENCE:\n{evidence_block(evidence)}\n\nReturn JSON with this shape:\n{SCHEMA}"
    )
    return SYSTEM_RULES, user
