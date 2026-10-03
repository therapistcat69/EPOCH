from app.prompts.common import SYSTEM_RULES, evidence_block

SCHEMA = '{"sections": [{"index": number, "topic": "2-5 word topic", "summary": "one sentence"}]}'


def build_section_label_prompt(title: str, sections: list[dict]) -> tuple[str, str]:
    user = (
        "Label each transcript section of the video with a short topic and a one-sentence summary. "
        "The transcript may be English, Hindi or Hinglish; write labels in English. Describe only what is said; "
        "do not add facts. Return exactly one entry per input section, keeping its index.\n\n"
        f"VIDEO TITLE: {title}\nSECTIONS:\n{evidence_block(sections)}\n\nReturn JSON with this shape:\n{SCHEMA}"
    )
    return SYSTEM_RULES, user
