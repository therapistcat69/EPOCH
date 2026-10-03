from app.prompts.common import SYSTEM_RULES, evidence_block

EXTRA_RULES = """
Additional rules for explaining an ML retention model:
- The numbers (predicted retention, risk scores, timestamps, contributing features) come from the model. Repeat them exactly; never alter, round differently, or invent any.
- Say "the model predicts" / "the model's attribution" - never claim that a feature CAUSES viewers to leave.
- If `trained_on` is synthetic, state once that the model was trained on synthetic development data and is not validated on real YouTube retention.
- Use only the transcript snippets provided to describe what is being said. One entry per supplied risk region, same start/end seconds."""

SCHEMA = """{
  "summary": "string (2-3 sentences about the overall predicted curve and the risk regions)",
  "risk_explanations": [
    {"start_seconds": number, "end_seconds": number,
     "what_is_happening": "string: what the transcript says there and which model-attributed features stand out",
     "possible_experiment": "string: an editorial experiment to test (phrased as 'Consider testing ...')"}
  ]
}"""


def build_ml_explanation_prompt(evidence: dict) -> tuple[str, str]:
    user = (
        "Explain this retention prediction for a creator.\n\n"
        f"EVIDENCE:\n{evidence_block(evidence)}\n\nReturn JSON with this shape:\n{SCHEMA}"
    )
    return SYSTEM_RULES + EXTRA_RULES, user
