"""Transcript + metadata -> per-segment feature table (schema version FEATURE_SCHEMA_VERSION).

The SAME function is used for training data and for inference, so preprocessing cannot drift between them.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import config
from src.features import schema
from src.features.emotion import emotion_features
from src.features.engagement import engagement_features
from src.features.hook import hook_features
from src.features.information_density import information_features
from src.features.linguistic import linguistic_features, words
from src.features.repetition import repetition_features
from src.features.similarity import similarity_context
from src.features.title import title_features
from src.features.topics import topic_features
from src.preprocessing import Transcript, canonicalize, segment_transcript


@dataclass
class VideoFeatures:
    video_id: str
    table: pd.DataFrame      # META_COLUMNS + all pre-publication feature columns (+ optional context columns)
    embeddings: np.ndarray   # (n_segments, d) segment embeddings
    title_embedding: np.ndarray
    duration: float
    segment_seconds: float
    schema_version: str = schema.FEATURE_SCHEMA_VERSION


def _context_features(df: pd.DataFrame) -> pd.DataFrame:
    """Optional cumulative-history features (causal). Off by default (see schema.OPTIONAL_GROUPS)."""
    n = len(df)
    cum_red = df["redundant_information_score"].expanding().mean().to_numpy()
    cum_inf = df["information_density"].expanding().mean().to_numpy()
    last_topic, last_emo = 0.0, 0.0
    since_topic, since_emo = [], []
    for i in range(n):
        if df["topic_change_score"].iat[i] > 0.5:
            last_topic = df["start_time"].iat[i]
        if df["emotional_intensity"].iat[i] > 0.4:
            last_emo = df["start_time"].iat[i]
        since_topic.append(df["start_time"].iat[i] - last_topic)
        since_emo.append(df["start_time"].iat[i] - last_emo)
    return pd.DataFrame(dict(cum_mean_redundancy=cum_red, cum_mean_information_density=cum_inf,
                             time_since_last_topic_change=since_topic, time_since_last_high_emotion=since_emo), index=df.index)


def build_video_features(video_id: str, title: str, description: str, duration: float, raw_segments: list[dict], embedder,
                         segment_seconds: float = config.DEFAULT_SEGMENT_SECONDS, transcript: Transcript | None = None) -> VideoFeatures:
    tr = transcript or canonicalize(video_id, raw_segments, duration)
    segs = segment_transcript(tr, segment_seconds, duration)
    n = len(segs)
    texts = [s.text for s in segs]
    empty = np.array([s.is_empty for s in segs], dtype=bool)

    emb = embedder.encode(texts)
    title_emb = embedder.encode([title or ""])[0]
    sim = similarity_context(emb, empty)

    base_rows = []
    for s in segs:
        dur = max(s.end_time - s.start_time, 1e-6)
        row = dict(video_id=video_id, segment_id=s.segment_id, start_time=s.start_time, end_time=s.end_time, text=s.text)
        row.update(absolute_time=s.absolute_time, relative_position=s.relative_position, segment_index=s.segment_id)
        row.update(linguistic_features(s.text, dur))
        row.update(engagement_features(s.text))
        row.update(emotion_features(s.text))
        base_rows.append(row)

    rep = repetition_features(texts, sim, empty)
    info = information_features(texts, [r["lexical_diversity"] for r in base_rows], sim, empty)
    top = topic_features(emb, sim, empty)
    ttl = title_features(title_emb, emb, [s.start_time for s in segs], empty, duration)
    for r, a, b, c, d in zip(base_rows, rep, info, top, ttl):
        r.update(a); r.update(b); r.update(c); r.update(d)

    hooks = hook_features(base_rows, texts, duration, ttl[0]["promise_gap_seconds"] if ttl else duration)
    video_level = dict(
        duration_seconds=float(duration), title_word_count=len(words(title)), description_word_count=len(words(description)),
        title_has_question=int("?" in (title or "")), title_has_number=int(any(ch.isdigit() for ch in (title or ""))),
    )
    for r in base_rows:
        r.update(hooks)
        r.update(video_level)
    df = pd.DataFrame(base_rows)
    for col in schema.PRE_PUBLICATION_FEATURES:
        if col not in df.columns:
            raise RuntimeError(f"feature pipeline did not produce column {col!r}")
    ctx = _context_features(df)
    df = pd.concat([df[schema.META_COLUMNS + schema.PRE_PUBLICATION_FEATURES], ctx], axis=1)
    return VideoFeatures(video_id, df, emb, title_emb, float(duration), float(segment_seconds))
