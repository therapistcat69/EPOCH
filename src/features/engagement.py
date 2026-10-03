"""Engagement-style descriptive features (not assumed causal)."""
import re

from src.features.linguistic import sentences, words

ENGAGEMENT_COLUMNS = [
    "question_count", "exclamation_count", "imperative_sentence_count", "direct_audience_address", "cta_indicator",
    "conversational_language", "question_density", "exclamation_density",
]

_IMPERATIVE_STARTS = {"let", "let's", "lets", "go", "check", "look", "try", "watch", "make", "subscribe", "smash", "drop", "share", "use", "click",
                      "hit", "stay", "remember", "don't", "dont", "keep", "take", "grab", "wait", "come", "follow", "comment", "turn", "leave"}
_AUDIENCE = {"you", "your", "you're", "youre", "yours", "guys", "everyone", "everybody", "chat", "y'all", "folks", "viewers"}
_CTA = re.compile(r"\b(subscribe|like button|smash|notification|comment (below|down)|drop a comment|share (this|it)|link in the description|use code|sponsored|discount)\b", re.I)
_CONVERSATIONAL = re.compile(r"\b(um|uh|like|you know|i mean|basically|honestly|kind of|sort of|right|okay|so yeah|anyway|dude|bro|literally)\b", re.I)
_CONTRACTION = re.compile(r"\w+'(s|re|ve|ll|d|m|t)\b", re.I)


def engagement_features(text: str) -> dict:
    sents = sentences(text)
    w = words(text)
    n = max(len(w), 1)
    ns = max(len(sents), 1)
    q = (text or "").count("?")
    ex = (text or "").count("!")
    imper = sum(1 for s in sents if (words(s)[:1] or [""])[0] in _IMPERATIVE_STARTS)
    addr = sum(1 for x in w if x in _AUDIENCE)
    cta = len(_CTA.findall(text or ""))
    conv = (len(_CONVERSATIONAL.findall(text or "")) + len(_CONTRACTION.findall(text or ""))) / n
    return dict(
        question_count=q, exclamation_count=ex, imperative_sentence_count=imper, direct_audience_address=addr,
        cta_indicator=int(cta > 0), conversational_language=conv, question_density=q / ns, exclamation_density=ex / ns,
    )
