"""Format detection and data-derived title patterns, shared by channel analysis, trends and benchmarks.

Formats use a small, transparent cue lexicon (English + common Hindi/Hinglish cues) - a heuristic, listed
in code so it can be reviewed and extended. Title patterns are DERIVED from the data (frequent leading
n-grams and structural features), not hard-coded phrase lists.
"""
import re
from collections import Counter

from app.services.nlp import leading_ngram

FORMAT_CUES: dict[str, re.Pattern] = {
    "Comparison": re.compile(r"\bvs\.?\b|\bversus\b|\bcompar|\bbetter than\b|\bwhich is (better|best)\b|बनाम", re.I),
    "Tutorial": re.compile(r"\bhow to\b|\btutorial\b|\bstep[- ]by[- ]step\b|\bguide\b|\blearn\b|\bcourse\b|\bbeginner|कैसे|सीखें|\bseekho\b|\bsikho\b", re.I),
    "Review": re.compile(r"\breview\b|\bunboxing\b|\bhonest\b|\bworth it\b|\bhands[- ]on\b|\bfirst impressions?\b", re.I),
    "Listicle": re.compile(r"^\s*(top\s+)?\d+\s+\w+|\btop\s+\d+\b|\b\d+\s+(best|ways|tools|tips|things|reasons|mistakes|apps)\b", re.I),
    "Challenge": re.compile(r"\bchallenge\b|\bi tried\b|\bwe tried\b|\b\d+\s*days?\b.*\b(challenge|try|tried)\b", re.I),
    "Case Study": re.compile(r"\bcase study\b|\bhow (i|we) (built|made|grew|got)\b|\bbehind the scenes\b", re.I),
    "Live Build": re.compile(r"\b(i|we) built\b|\bbuilding\b|\blive (coding|build|stream)\b|\bbuild (a|an|my)\b", re.I),
    "News / Update": re.compile(r"\bnews\b|\bupdate\b|\bannounc|\blaunch(ed|es)?\b|\breleased?\b|\bnew\b.*\b(model|version)\b", re.I),
    "Vlog": re.compile(r"\bvlog\b|\bday in (my|the) life\b|\bmy (week|day|trip)\b", re.I),
}


def detect_format(title: str, description: str | None = None) -> str | None:
    """First matching format in priority order (title first, then description); None if no cue."""
    for text in (title or "", (description or "")[:300]):
        for name, pat in FORMAT_CUES.items():
            if pat.search(text):
                return name
    return None


def structural_features(title: str) -> list[str]:
    feats = []
    if re.search(r"\bvs\.?\b|\bversus\b", title, re.I):
        feats.append("X vs Y")
    if re.match(r"^\s*\d+", title):
        feats.append("Starts with a number")
    if "?" in title:
        feats.append("Question")
    if re.search(r"\b20\d{2}\b", title):
        feats.append("Contains a year")
    if re.search(r"[\[(|]", title):
        feats.append("Brackets / pipe separator")
    if re.search(r"\b(complete|ultimate|full) (guide|course|tutorial)\b", title, re.I):
        feats.append("Complete guide")
    if re.search(r"\bi (tried|built|made|tested|switched)\b", title, re.I):
        feats.append("First-person experiment")
    return feats


def derive_title_patterns(titles: list[str], min_count: int = 2, top: int = 6) -> list[dict]:
    """Frequent leading n-grams + structural features across the sample (data-derived)."""
    n = len(titles)
    if n == 0:
        return []
    counts: Counter[str] = Counter()
    for t in titles:
        seen: set[str] = set()
        for k in (3, 2):
            g = leading_ngram(t, k)
            if g:
                seen.add(f"Starts with “{g}”")
                break  # prefer the longest match per title
        seen.update(structural_features(t))
        counts.update(seen)
    items = [{"pattern": p, "count": c, "share": round(c / n, 3)} for p, c in counts.items() if c >= min_count]
    return sorted(items, key=lambda x: (-x["count"], x["pattern"]))[:top]


def format_distribution(titles_descs: list[tuple[str, str | None]]) -> list[dict]:
    counts: Counter[str] = Counter()
    for title, desc in titles_descs:
        counts[detect_format(title, desc) or "Other / unclassified"] += 1
    n = sum(counts.values()) or 1
    return [{"format": f, "count": c, "share": round(c / n, 3)} for f, c in counts.most_common()]
