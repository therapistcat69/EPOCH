"""Deterministic transcript CONTENT features. These are NOT retention predictions.

Heuristic definitions (all transparent):
- semantic_novelty      = 1 - max TF-IDF cosine similarity to any earlier segment.
- repetition_score      = max cosine similarity to an earlier, non-adjacent segment. >= REPEAT_THRESHOLD is flagged.
- information_density   = (content-word share) * (0.5 + 0.5 * novelty), in [0, 1].
- contains_new_information = novelty >= 0.5 and at least 4 content words.
- is_hook               = within the first HOOK_WINDOW seconds and (question | number | hook phrase | title keyword).
- topic_reveal          = first segment sharing a content word with the title.
- promise_start         = first segment where a 3-segment window covers >= 50% of the title's content words.
Similarity is lexical (no embeddings); the interface allows swapping in an embedding model later.
"""
import re
from statistics import median

from pydantic import BaseModel

from app.schemas.transcript import SegmentIn
from app.services import nlp

FEATURE_SCHEMA_VERSION = "1.0"
REPEAT_THRESHOLD = 0.55
HOOK_WINDOW = 30.0

_QUESTION_START = re.compile(
    r"^\s*(what|why|how|when|where|who|which|is|are|do|does|did|can|could|should|will|would|क्या|कैसे|क्यों|कौन|kya|kaise|kyun|kyu)\b", re.I
)
_HOOK_PHRASES = re.compile(
    r"\b(in this video|today|you'?ll learn|by the end|here'?s (why|how|what)|secret|mistake|never|stop|"
    r"imagine|what if|the (truth|reason)|you need to know|let me show)\b|आज|इस वीडियो", re.I
)
CTA_PATTERNS: dict[str, re.Pattern] = {
    "subscribe": re.compile(r"\bsubscribe\b|\bbell icon\b|सब्सक्राइब|\bsubscribe karo\b|\bchannel ko\b.*\bsubscribe", re.I),
    "like": re.compile(r"\b(hit|smash|drop|leave|give)\b.{0,15}\blike\b|\blike (the|this) video\b|\blike karo\b|\blike button\b", re.I),
    "comment": re.compile(r"\b(let me know|tell me|drop|leave|write)\b.{0,25}\bcomments?\b|\bcomment (below|down)\b|\bcomment karo\b", re.I),
    "share": re.compile(r"\bshare (this|the) video\b|\bshare it\b|\bshare karo\b", re.I),
    "link": re.compile(r"\blink (is |in |down )?(in )?(the )?(description|below|bio)\b|\bcheck (out )?(the )?link\b|\bin the description\b|\bhttps?://", re.I),
    "product": re.compile(r"\b(sponsor(ed)?|discount|promo code|use code|coupon|affiliate|buy (it|now)|sale|offer)\b", re.I),
}


class SegmentFeatures(BaseModel):
    segment_id: int
    start: float
    end: float
    text: str
    topic: str | None = None  # filled by the optional Groq labelling step
    summary: str | None = None
    is_hook: bool
    is_question: bool
    is_cta: bool
    cta_types: list[str] = []
    contains_new_information: bool
    repetition_score: float
    topic_change: bool
    semantic_novelty: float
    information_density: float
    words_per_minute: float | None = None


class RepeatedIdea(BaseModel):
    start: float
    end: float
    similar_to: list[dict]
    similarity: float


class CTA(BaseModel):
    type: str
    start: float
    end: float
    text: str


class TranscriptAnalysis(BaseModel):
    feature_schema_version: str = FEATURE_SCHEMA_VERSION
    segment_count: int
    duration_seconds: float
    # hook / promise
    hook_latency_seconds: float | None = None
    first_payoff_seconds: float | None = None
    first_topic_reveal_seconds: float | None = None
    promise_gap_seconds: float | None = None
    # pacing
    average_words_per_minute: float | None = None
    sentences_per_minute: float | None = None
    mean_segment_seconds: float | None = None
    median_segment_seconds: float | None = None
    topic_transitions: int = 0
    silence_rate: float | None = None  # needs audio; None = data unavailable
    # aggregate content features
    repetition_score: float | None = None
    semantic_novelty: float | None = None
    information_density: float | None = None
    repeated_ideas: list[RepeatedIdea] = []
    ctas: list[CTA] = []
    segments: list[SegmentFeatures]


def _vector_sum(vectors: list[nlp.Vector]) -> nlp.Vector:
    out: nlp.Vector = {}
    for v in vectors:
        for t, x in v.items():
            out[t] = out.get(t, 0.0) + x
    return out


def analyze_transcript(
    segments: list[SegmentIn], title: str, description: str | None = None, duration_seconds: float | None = None
) -> TranscriptAnalysis:
    segs = sorted(segments, key=lambda s: s.start_seconds)
    duration = duration_seconds or (segs[-1].end_seconds if segs else 0.0)
    token_lists = [nlp.tokenize(s.text) for s in segs]
    title_tokens = set(nlp.tokenize(title))
    idf = nlp.build_idf(token_lists + [list(title_tokens)])
    vecs = [nlp.vectorize(t, idf) for t in token_lists]

    features: list[SegmentFeatures] = []
    repeated: list[RepeatedIdea] = []
    ctas: list[CTA] = []
    for i, s in enumerate(segs):
        sims = [(nlp.cosine(vecs[i], vecs[j]), j) for j in range(i)]
        max_sim = max((x for x, _ in sims), default=0.0)
        novelty = 1.0 if i == 0 else round(1.0 - max_sim, 4)
        far = [(x, j) for x, j in sims if j < i - 1]  # exclude the adjacent segment (natural continuity)
        rep, rep_j = max(far, default=(0.0, -1))
        words = nlp.word_count(s.text)
        content = len(token_lists[i])
        density = round(min(1.0, (content / words if words else 0.0)) * (0.5 + 0.5 * novelty), 4)
        dur = max(s.end_seconds - s.start_seconds, 0.001)
        types = [name for name, pat in CTA_PATTERNS.items() if pat.search(s.text)]
        is_q = "?" in s.text or bool(_QUESTION_START.match(s.text))
        in_window = s.start_seconds <= HOOK_WINDOW
        overlap = bool(title_tokens & set(token_lists[i]))
        is_hook = in_window and (is_q or bool(re.search(r"\d", s.text)) or bool(_HOOK_PHRASES.search(s.text)) or overlap) and not types
        prev_window = _vector_sum(vecs[max(0, i - 3) : i])
        change = i >= 2 and nlp.cosine(prev_window, vecs[i]) < 0.05 and content >= 3

        features.append(
            SegmentFeatures(
                segment_id=s.segment_index, start=s.start_seconds, end=s.end_seconds, text=s.text,
                is_hook=is_hook, is_question=is_q, is_cta=bool(types), cta_types=types,
                contains_new_information=novelty >= 0.5 and content >= 4,
                repetition_score=round(rep, 4), topic_change=change, semantic_novelty=novelty,
                information_density=density, words_per_minute=round(words / dur * 60, 1) if words >= 3 else None,
            )
        )
        for t in types:
            ctas.append(CTA(type=t, start=s.start_seconds, end=s.end_seconds, text=s.text))
        if rep >= REPEAT_THRESHOLD and rep_j >= 0:
            partner = segs[rep_j]
            repeated.append(
                RepeatedIdea(
                    start=s.start_seconds, end=s.end_seconds, similarity=round(rep, 3),
                    similar_to=[{"start": partner.start_seconds, "end": partner.end_seconds}],
                )
            )

    # --- hook / promise -------------------------------------------------------
    hook = next((f.start for f in features if f.is_hook), None)
    payoff = next((f.start for f in features if f.contains_new_information and f.information_density >= 0.6 and not f.is_cta), None)
    reveal = next((s.start_seconds for s, t in zip(segs, token_lists) if title_tokens & set(t)), None) if title_tokens else None
    promise = None
    if title_tokens:
        need = max(1, round(len(title_tokens) * 0.5))
        for i, s in enumerate(segs):
            window = set().union(*token_lists[i : i + 3]) if token_lists[i : i + 3] else set()
            if len(title_tokens & window) >= need:
                promise = s.start_seconds
                break

    # --- pacing -----------------------------------------------------------------
    total_words = sum(nlp.word_count(s.text) for s in segs)
    sentences = sum(max(1, len(re.findall(r"[.!?।]+", s.text))) for s in segs)
    seg_lens = [s.end_seconds - s.start_seconds for s in segs]
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None  # noqa: E731

    return TranscriptAnalysis(
        segment_count=len(segs), duration_seconds=round(duration, 2),
        hook_latency_seconds=hook, first_payoff_seconds=payoff, first_topic_reveal_seconds=reveal, promise_gap_seconds=promise,
        average_words_per_minute=round(total_words / (duration / 60), 1) if duration > 0 else None,
        sentences_per_minute=round(sentences / (duration / 60), 1) if duration > 0 else None,
        mean_segment_seconds=round(sum(seg_lens) / len(seg_lens), 2) if seg_lens else None,
        median_segment_seconds=round(median(seg_lens), 2) if seg_lens else None,
        topic_transitions=sum(1 for f in features if f.topic_change),
        repetition_score=mean([f.repetition_score for f in features]),
        semantic_novelty=mean([f.semantic_novelty for f in features]),
        information_density=mean([f.information_density for f in features]),
        repeated_ideas=repeated, ctas=ctas, segments=features,
    )


def segments_at(analysis_segments: list[SegmentFeatures], start: float, end: float) -> list[SegmentFeatures]:
    """Segments overlapping [start, end] (used to link observed drop-offs to what was being said)."""
    return [s for s in analysis_segments if s.end >= start and s.start <= end]
