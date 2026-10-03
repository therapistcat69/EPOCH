from app.prompts.common import SYSTEM_RULES, evidence_block

SCHEMA = """{
  "summary": "string",
  "observed_opportunities": [
    {"title": "string", "evidence": ["string quoting the supplied numbers"], "suggested_experiment": "string"}
  ],
  "caveats": ["string"]
}"""


def build_trend_report_prompt(evidence: dict) -> tuple[str, str]:
    user = (
        "Summarise the visible content patterns for this genre sample. The data is a sample of recent PUBLIC "
        "YouTube videos found via search; momentum values are RetainAI-derived (not YouTube trend scores). "
        "Start opportunities with wording like 'Observed public YouTube content in the selected sample shows ...'. "
        "Never say YouTube wants or favours anything.\n\n"
        f"EVIDENCE:\n{evidence_block(evidence)}\n\nReturn JSON with this shape:\n{SCHEMA}"
    )
    return SYSTEM_RULES, user
