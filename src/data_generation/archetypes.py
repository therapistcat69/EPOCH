"""Archetype priors for the synthetic generator.

Each archetype gives a mean for every latent trait plus a base mix over content events. A *family* (template
family) is an archetype + a fixed per-family trait offset, so whole families can be held out for validation/test:
the test set then contains unseen combinations of hook strength, pacing, repetition, topic structure and payoff
timing. These numbers are generator ASSUMPTIONS, not measurements of real YouTube behaviour.
"""
from dataclasses import dataclass, field

TRAITS = (
    "hook_strength",      # 0..1  strong teaser of what is coming in the opening
    "intro_length",       # seconds of preamble before the main content
    "pacing",             # 0..1  maps to 110..210 words per minute
    "information_density",# 0..1  share of content cues that carry concrete information
    "repetition",         # 0..1  tendency to restate earlier ideas
    "novelty",            # 0..1  probability a content cue introduces a NEW idea
    "topic_shift",        # 0..1  rate of abrupt topic changes
    "suspense",           # 0..1  weight of suspense-building cues before payoffs
    "emotional_intensity",# 0..1
    "payoff_latency",     # seconds until the first real payoff
    "payoff_rate",        # payoffs per minute after the first
    "sponsor_prob",       # probability a sponsor block exists
    "sponsor_intrusiveness",  # 0..1 how disruptive the sponsor read is
    "filler",             # 0..1  filler-word / filler-cue tendency
    "energetic",          # 0..1  probability the style is exclamation-heavy
)

RANGES = {
    "hook_strength": (0, 1), "intro_length": (3, 75), "pacing": (0, 1), "information_density": (0, 1),
    "repetition": (0, 0.9), "novelty": (0.1, 1), "topic_shift": (0, 0.8), "suspense": (0, 1),
    "emotional_intensity": (0, 1), "payoff_latency": (8, 200), "payoff_rate": (0.2, 2.5),
    "sponsor_prob": (0, 1), "sponsor_intrusiveness": (0, 1), "filler": (0, 0.9), "energetic": (0, 1),
}

CONTENT_EVENTS = ("GAMEPLAY_ACTION", "COMMENTARY", "SUSPENSE", "FAIL", "JOKE", "EXPLAIN")


@dataclass(frozen=True)
class Archetype:
    name: str
    traits: dict
    mix: dict = field(default_factory=dict)  # base weights over content events
    cue_seconds: tuple = (5.0, 9.0)


ARCHETYPES: dict[str, Archetype] = {a.name: a for a in [
    Archetype("fast_challenge",
              dict(hook_strength=.8, intro_length=10, pacing=.8, information_density=.45, repetition=.12, novelty=.75, topic_shift=.12,
                   suspense=.7, emotional_intensity=.8, payoff_latency=35, payoff_rate=1.2, sponsor_prob=.3, sponsor_intrusiveness=.5,
                   filler=.15, energetic=.9),
              dict(GAMEPLAY_ACTION=.35, SUSPENSE=.25, FAIL=.15, JOKE=.1, COMMENTARY=.1, EXPLAIN=.05), (4.0, 7.0)),
    Archetype("gameplay_commentary",
              dict(hook_strength=.35, intro_length=30, pacing=.5, information_density=.4, repetition=.25, novelty=.5, topic_shift=.15,
                   suspense=.3, emotional_intensity=.45, payoff_latency=90, payoff_rate=.5, sponsor_prob=.4, sponsor_intrusiveness=.5,
                   filler=.4, energetic=.4),
              dict(GAMEPLAY_ACTION=.3, COMMENTARY=.35, JOKE=.1, SUSPENSE=.1, FAIL=.05, EXPLAIN=.1), (6.0, 10.0)),
    Archetype("story_driven",
              dict(hook_strength=.55, intro_length=22, pacing=.4, information_density=.6, repetition=.15, novelty=.7, topic_shift=.2,
                   suspense=.6, emotional_intensity=.65, payoff_latency=110, payoff_rate=.35, sponsor_prob=.3, sponsor_intrusiveness=.4,
                   filler=.2, energetic=.25),
              dict(COMMENTARY=.4, SUSPENSE=.25, EXPLAIN=.15, GAMEPLAY_ACTION=.15, JOKE=.03, FAIL=.02), (7.0, 11.0)),
    Archetype("tutorial_guide",
              dict(hook_strength=.5, intro_length=18, pacing=.55, information_density=.85, repetition=.2, novelty=.75, topic_shift=.18,
                   suspense=.1, emotional_intensity=.25, payoff_latency=45, payoff_rate=.4, sponsor_prob=.35, sponsor_intrusiveness=.4,
                   filler=.15, energetic=.2),
              dict(EXPLAIN=.55, GAMEPLAY_ACTION=.2, COMMENTARY=.15, FAIL=.05, JOKE=.03, SUSPENSE=.02), (6.0, 10.0)),
    Archetype("reaction",
              dict(hook_strength=.45, intro_length=25, pacing=.7, information_density=.25, repetition=.3, novelty=.45, topic_shift=.3,
                   suspense=.2, emotional_intensity=.75, payoff_latency=60, payoff_rate=.9, sponsor_prob=.4, sponsor_intrusiveness=.6,
                   filler=.35, energetic=.8),
              dict(COMMENTARY=.4, JOKE=.3, GAMEPLAY_ACTION=.1, SUSPENSE=.05, FAIL=.05, EXPLAIN=.1), (4.0, 8.0)),
    Archetype("tournament_highlights",
              dict(hook_strength=.7, intro_length=12, pacing=.75, information_density=.5, repetition=.1, novelty=.8, topic_shift=.25,
                   suspense=.55, emotional_intensity=.85, payoff_latency=40, payoff_rate=1.5, sponsor_prob=.25, sponsor_intrusiveness=.3,
                   filler=.1, energetic=.85),
              dict(GAMEPLAY_ACTION=.4, SUSPENSE=.2, COMMENTARY=.15, JOKE=.05, EXPLAIN=.15, FAIL=.05), (4.0, 7.0)),
    Archetype("boss_fight",
              dict(hook_strength=.7, intro_length=15, pacing=.6, information_density=.4, repetition=.3, novelty=.5, topic_shift=.08,
                   suspense=.85, emotional_intensity=.9, payoff_latency=150, payoff_rate=.3, sponsor_prob=.25, sponsor_intrusiveness=.4,
                   filler=.15, energetic=.6),
              dict(SUSPENSE=.35, FAIL=.25, GAMEPLAY_ACTION=.25, COMMENTARY=.08, EXPLAIN=.05, JOKE=.02), (5.0, 8.0)),
    Archetype("funny_montage",
              dict(hook_strength=.6, intro_length=8, pacing=.85, information_density=.2, repetition=.15, novelty=.7, topic_shift=.35,
                   suspense=.15, emotional_intensity=.8, payoff_latency=25, payoff_rate=2.0, sponsor_prob=.15, sponsor_intrusiveness=.3,
                   filler=.1, energetic=.95),
              dict(JOKE=.45, FAIL=.25, GAMEPLAY_ACTION=.2, COMMENTARY=.08, EXPLAIN=.01, SUSPENSE=.01), (3.5, 6.0)),
    Archetype("strategy_explanation",
              dict(hook_strength=.4, intro_length=28, pacing=.45, information_density=.9, repetition=.35, novelty=.6, topic_shift=.2,
                   suspense=.05, emotional_intensity=.2, payoff_latency=70, payoff_rate=.3, sponsor_prob=.45, sponsor_intrusiveness=.5,
                   filler=.25, energetic=.15),
              dict(EXPLAIN=.6, COMMENTARY=.2, GAMEPLAY_ACTION=.1, FAIL=.05, JOKE=.03, SUSPENSE=.02), (7.0, 11.0)),
    Archetype("review_style",
              dict(hook_strength=.4, intro_length=35, pacing=.5, information_density=.7, repetition=.3, novelty=.55, topic_shift=.28,
                   suspense=.1, emotional_intensity=.35, payoff_latency=120, payoff_rate=.25, sponsor_prob=.5, sponsor_intrusiveness=.55,
                   filler=.3, energetic=.3),
              dict(COMMENTARY=.4, EXPLAIN=.4, GAMEPLAY_ACTION=.1, JOKE=.05, FAIL=.03, SUSPENSE=.02), (6.0, 10.0)),
]}

FAMILIES_PER_ARCHETYPE = 6
VIDEOS_PER_FAMILY = 7  # 10 archetypes x 6 families x 7 videos = 420 videos
