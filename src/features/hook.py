"""Opening / hook features (video-level numbers, broadcast to every segment). All derived, none hand-labelled good/bad.

Fixed a-priori constants (never tuned on a test set):
    intro_length            = start of the first segment with greeting_score < 0.12 AND information_density >= 0.35
    time_to_first_action    = start of the first segment with action_density >= 0.04
    time_to_first_payoff    = start of the first segment with payoff hits >= 2, or >= 1 and >= 2 exclamation marks
    time_to_main_topic      = promise_gap_seconds (see title.py)
    opening_*               = mean over segments that start within the first 30 s
    hook_strength           = mean( opening_teaser, opening_emotional_intensity, opening_information_density,
                                    1 - min(intro_length, 60) / 60 )
where opening_teaser = fraction of opening segments containing a question or a teaser phrase ("by the end", "what if",
"stay until", "challenge", "never tried").  If an event never happens the time is set to the video duration.
"""
import re

from src.features.linguistic import words

HOOK_COLUMNS = ["intro_length", "time_to_first_action", "time_to_first_payoff", "time_to_main_topic", "opening_information_density",
                "opening_emotional_intensity", "hook_strength"]

_GREETING = {"hey", "welcome", "back", "channel", "subscribe", "subscribed", "notifications", "guys", "everybody", "everyone", "support",
             "thanks", "thank", "update", "shout", "anyway", "week", "hope", "while"}
_ACTION = {"run", "sprint", "grab", "swing", "roll", "attack", "jump", "shoot", "hit", "dodge", "fight", "cut", "move", "heading", "switching",
           "using", "rolling", "sprinting", "grabbing", "swinging", "cutting", "spots", "lands"}
_PAYOFF = re.compile(r"\b(yes|we did it|we got it|got it|is down|no way|finally|first try|cannot believe|can't believe|flawless|victory|we actually did it)\b", re.I)
_TEASER = re.compile(r"\b(by the end|what if|stay until|challenge|never tried|impossible|attempting|i might not|did not expect|going to)\b|\?", re.I)

OPEN_WINDOW = 30.0


def greeting_score(text: str) -> float:
    w = words(text)
    return sum(1 for x in w if x in _GREETING) / max(len(w), 1)


def action_density(text: str) -> float:
    w = words(text)
    return sum(1 for x in w if x in _ACTION) / max(len(w), 1)


def payoff_hits(text: str) -> int:
    return len(_PAYOFF.findall(text or ""))


def hook_features(df_rows: list[dict], texts: list[str], duration: float, promise_gap_seconds: float) -> dict:
    """df_rows: per-segment dicts with start_time, information_density, emotional_intensity, exclamation_count."""
    def first(pred):
        for r, t in zip(df_rows, texts):
            if pred(r, t):
                return r["start_time"]
        return duration

    intro = first(lambda r, t: bool(t.strip()) and greeting_score(t) < 0.12 and r["information_density"] >= 0.35)
    action = first(lambda r, t: action_density(t) >= 0.04)
    payoff = first(lambda r, t: payoff_hits(t) >= 2 or (payoff_hits(t) >= 1 and r["exclamation_count"] >= 2))
    opening = [(r, t) for r, t in zip(df_rows, texts) if r["start_time"] < OPEN_WINDOW and t.strip()]
    if opening:
        o_info = sum(r["information_density"] for r, _ in opening) / len(opening)
        o_emo = sum(r["emotional_intensity"] for r, _ in opening) / len(opening)
        o_teaser = sum(1 for _, t in opening if _TEASER.search(t)) / len(opening)
    else:
        o_info = o_emo = o_teaser = 0.0
    hook = (o_teaser + o_emo + o_info + (1 - min(intro, 60.0) / 60.0)) / 4.0
    return dict(intro_length=float(intro), time_to_first_action=float(action), time_to_first_payoff=float(payoff),
                time_to_main_topic=float(promise_gap_seconds), opening_information_density=float(o_info),
                opening_emotional_intensity=float(o_emo), hook_strength=float(hook))
