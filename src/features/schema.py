"""Versioned feature schema with an explicit pre-/post-publication split (leakage guard).

The retention-prediction model may use PRE_PUBLICATION_FEATURES only. POST_PUBLICATION_FEATURES (views, likes,
comments, actual retention, subscribers gained) exist for analysis/validation and are never predictor inputs.
"""
from src import config
from src.features.emotion import EMOTION_COLUMNS
from src.features.engagement import ENGAGEMENT_COLUMNS
from src.features.hook import HOOK_COLUMNS
from src.features.information_density import INFORMATION_COLUMNS
from src.features.linguistic import LINGUISTIC_COLUMNS
from src.features.repetition import REPETITION_COLUMNS
from src.features.title import TITLE_COLUMNS
from src.features.topics import TOPIC_COLUMNS

FEATURE_SCHEMA_VERSION = config.FEATURE_SCHEMA_VERSION

POSITION_COLUMNS = ["absolute_time", "relative_position", "segment_index"]
VIDEO_COLUMNS = ["duration_seconds", "title_word_count", "description_word_count", "title_has_question", "title_has_number"]
CONTEXT_COLUMNS = ["cum_mean_redundancy", "cum_mean_information_density", "time_since_last_topic_change", "time_since_last_high_emotion"]

FEATURE_GROUPS = {
    "position": POSITION_COLUMNS,
    "video": VIDEO_COLUMNS,
    "linguistic": LINGUISTIC_COLUMNS,
    "engagement": ENGAGEMENT_COLUMNS,
    "emotion": EMOTION_COLUMNS,
    "repetition": REPETITION_COLUMNS,
    "information": INFORMATION_COLUMNS,
    "topic": TOPIC_COLUMNS,
    "hook": HOOK_COLUMNS,
    "title": TITLE_COLUMNS,
}
# 'context' (cumulative history features) is opt-in; the default model is a per-segment model without history.
OPTIONAL_GROUPS = {"context": CONTEXT_COLUMNS}

PRE_PUBLICATION_FEATURES = [c for cols in FEATURE_GROUPS.values() for c in cols]
POST_PUBLICATION_FEATURES = ["views", "likes", "comments", "subscribers_gained", "subscribers_lost", "actual_retention",
                             "average_view_percentage", "average_view_duration", "watch_time"]
META_COLUMNS = ["video_id", "segment_id", "start_time", "end_time", "text"]
TARGET_COLUMNS = ["retention_target", "drop_target"]


def assert_pre_publication(columns) -> None:
    bad = [c for c in columns if c in POST_PUBLICATION_FEATURES or c in TARGET_COLUMNS]
    if bad:
        raise ValueError(f"Data leakage: post-publication/target columns used as predictors: {bad}")


def group_of(feature: str) -> str:
    for g, cols in {**FEATURE_GROUPS, **OPTIONAL_GROUPS}.items():
        if feature in cols:
            return g
    return "embedding" if feature.startswith("emb_") else "other"


# Human-readable factor labels used in model-based explanations (descriptive, NOT causal).
FACTOR_LABELS = {
    "redundant_information_score": ("high redundancy with earlier content", "low redundancy with earlier content"),
    "similarity_with_earlier_segments": ("high similarity to earlier segments", "low similarity to earlier segments"),
    "similarity_with_recent_context": ("high similarity to the recent context", "low similarity to the recent context"),
    "semantic_novelty": ("high semantic novelty", "low semantic novelty"),
    "information_density": ("high information density", "low information density"),
    "new_term_ratio": ("many new terms", "few new terms"),
    "topic_change_score": ("abrupt topic change", "continuous topic"),
    "emotional_intensity": ("high emotional intensity", "low emotional intensity"),
    "speaking_rate": ("fast speaking rate", "slow speaking rate"),
    "relative_position": ("late position in the video", "early position in the video"),
    "absolute_time": ("later in the video", "earlier in the video"),
    "intro_length": ("long intro", "short intro"),
    "time_to_first_payoff": ("late first payoff", "early first payoff"),
    "promise_gap_seconds": ("long promise gap", "short promise gap"),
    "hook_strength": ("strong hook", "weak hook"),
    "conversational_language": ("conversational/filler language", "little conversational language"),
    "cta_indicator": ("call-to-action present", "no call-to-action"),
    "title_similarity": ("close to the title's topic", "far from the title's topic"),
    "exclamation_density": ("many exclamations", "few exclamations"),
    "question_density": ("many questions", "few questions"),
    "word_count": ("many words", "few words"),
}


def label_factor(feature: str, direction_high: bool) -> str:
    pair = FACTOR_LABELS.get(feature)
    if pair:
        return pair[0] if direction_high else pair[1]
    return f"{'high' if direction_high else 'low'} {feature.replace('_', ' ')}"
