"""Synthetic gaming transcript generator (caption-cue granularity).

Pipeline: sample latent traits -> schedule events over time (state machine) -> render text with templates ->
timestamps follow the speaking rate. The per-cue latent record (event type, novelty, repetition, ...) is returned
SEPARATELY and is generator-internal: it drives the retention simulator but must never be used as model input.
"""
import random
import zlib
from dataclasses import asdict, dataclass

import numpy as np

from src.data_generation import lexicon as L
from src.data_generation.archetypes import ARCHETYPES, RANGES, TRAITS, Archetype

EVENT_EMOTION = dict(PAYOFF=.9, SUSPENSE=.6, FAIL=.6, JOKE=.5, HOOK=.5, GAMEPLAY_ACTION=.4, TOPIC_SHIFT=.1,
                     COMMENTARY=.2, EXPLAIN=.15, SPONSOR=.05, CTA=.1, FILLER=.05, OUTRO=.1, INTRO_FLUFF=.1, RECAP=.15)


ONE_OFF_EVENTS = {"HOOK", "INTRO_FLUFF", "OUTRO", "SPONSOR", "CTA", "TOPIC_SHIFT"}


@dataclass
class CueLatent:
    segment_id: int
    event: str
    novelty: float      # 1 = brand-new idea, ~0 = restated
    repetition: float   # 1 = restates earlier content
    filler: float       # fraction of filler words
    emotion: float
    suspense: float
    words: int


def clip(v, lo, hi):
    return float(min(max(v, lo), hi))


def sample_traits(arch: Archetype, family_offset: dict, rng: np.random.Generator) -> dict:
    t = {}
    for k in TRAITS:
        lo, hi = RANGES[k]
        scale = (hi - lo)
        t[k] = clip(arch.traits[k] + (family_offset[k] + rng.normal(0, 0.08)) * scale, lo, hi)
    return t


def family_offset(archetype: str, family_idx: int, seed: int) -> dict:
    """Fixed per-family trait shifts (as a fraction of each trait's range) so families differ systematically."""
    # zlib.crc32 is stable across processes (Python's built-in hash() of str is randomized per run)
    rng = np.random.default_rng((zlib.crc32(f"{archetype}:{family_idx}".encode()) & 0xFFFFFFF) ^ seed)
    return {k: float(rng.normal(0, 0.14)) for k in TRAITS}


class _Slots:
    def __init__(self, game: str, rnd: random.Random):
        self.game, self.g, self.rnd = game, L.GAMES[game], rnd
        self.resample()

    def resample(self, partial: bool = False):
        r, g = self.rnd, self.g
        self.v = dict(game=self.game, enemy=r.choice(g["enemies"]), item=r.choice(g["items"]), place=r.choice(g["places"]),
                      mech=r.choice(g["mechs"]), adj=r.choice(L.ADJ), n=r.randint(12, 90), outcome=r.choice(L.OUTCOMES),
                      brand=r.choice(L.BRANDS), code=r.choice(L.CODES))

    def snapshot(self) -> dict:
        return dict(self.v)


def _render(template: str, slots: dict) -> str:
    return template.format(**slots)


def _count_words(s: str) -> int:
    return len(s.split())


def generate_video(video_id: str, archetype: str, family_idx: int, rng: np.random.Generator, seed: int) -> tuple[dict, list[dict], list[CueLatent], dict]:
    arch = ARCHETYPES[archetype]
    rnd = random.Random(int(rng.integers(0, 2**31 - 1)))
    traits = sample_traits(arch, family_offset(archetype, family_idx, seed), rng)
    game = rnd.choice(list(L.GAMES))
    slots = _Slots(game, rnd)
    wps = (110 + 100 * traits["pacing"]) / 60.0
    duration_target = float(rng.uniform(600, 900))
    energetic = rng.random() < traits["energetic"]

    sponsor = rng.random() < traits["sponsor_prob"]
    sponsor_start = float(rng.uniform(0.15, 0.55) * duration_target)
    sponsor_len = float(rng.uniform(25, 70))
    cta_mode = rnd.choices(["early", "mid", "end", "none"], weights=[.2, .25, .4, .15])[0]
    cta_time = {"early": rng.uniform(30, 70), "mid": duration_target * rng.uniform(.4, .6), "end": 1e9, "none": 1e9}[cta_mode]
    cta_done = False

    cues: list[dict] = []
    latents: list[CueLatent] = []
    ideas: list[dict] = []  # {kind, slots, variant, cue}
    used_templates: list[tuple] = []
    one_off_used: set[tuple] = set()
    t = 0.0
    next_payoff = traits["payoff_latency"]
    first_payoff_done = False

    def idea_sentence(kind=None, new=True, avoid_variant=None):
        if new or not ideas:
            kind = kind or rnd.choice(list(L.IDEAS))
            idea = dict(kind=kind, slots=slots.snapshot(), variant=rnd.randrange(3))
            ideas.append(idea)
        else:
            idea = rnd.choice(ideas)
        return idea

    def compose(event: str, target_words: float) -> tuple[str, float, float, bool]:
        """returns text, novelty, repetition, used_info"""
        nonlocal first_payoff_done
        sents: list[str] = []
        novelty, repetition = 0.65, 0.0
        sv = slots.snapshot()
        if event == "EXPLAIN" or event == "RECAP":
            if event == "RECAP" and len(ideas) >= 2:
                idea = rnd.choice(ideas[:-1])  # restate an earlier idea in different words
                variant = (idea["variant"] + rnd.choice([1, 2])) % 3
                sents.append(_render(L.IDEAS[idea["kind"]][variant], idea["slots"]))
                novelty, repetition = 0.05, 1.0
            else:
                fresh = rng.random() < traits["novelty"] or not ideas
                idea = idea_sentence(new=fresh)
                sents.append(_render(L.IDEAS[idea["kind"]][idea["variant"]], idea["slots"]))
                novelty = 1.0 if fresh else 0.25
                repetition = 0.0 if fresh else 0.6
        else:
            key = "EXPLAIN" if event == "EXPLAIN" else event
            templates = L.EVENTS.get(key, L.EVENTS["COMMENTARY"])
            idx = rnd.randrange(len(templates))
            if event in ONE_OFF_EVENTS:  # intro/outro/sponsor/CTA lines: do not say the same line twice in a video
                fresh_idx = [i for i in range(len(templates)) if (event, i) not in one_off_used]
                if fresh_idx:
                    idx = rnd.choice(fresh_idx)
                one_off_used.add((event, idx))
            same_event = [u for u in used_templates if u[0] == event]
            if same_event and rng.random() > traits["novelty"] and event in ("GAMEPLAY_ACTION", "COMMENTARY", "SUSPENSE", "JOKE", "FAIL"):
                ev0, idx0, sv0 = rnd.choice(same_event)  # low novelty: re-use an earlier line of the SAME event type
                sents.append(_render(L.EVENTS[ev0][idx0], sv0))
                novelty, repetition = 0.2, 0.7
            else:
                sents.append(_render(templates[idx], sv))
                used_templates.append((event, idx, sv))
                novelty = 0.7 if event in ("GAMEPLAY_ACTION", "COMMENTARY", "SUSPENSE", "JOKE", "FAIL") else 0.5
        words = _count_words(" ".join(sents))
        # pad with more sentences until the cue is long enough for its duration at the current speaking rate
        guard = 0
        while words < target_words * 0.8 and guard < 4 and event not in ONE_OFF_EVENTS:
            guard += 1
            if rng.random() < traits["information_density"] * 0.7 and event in ("GAMEPLAY_ACTION", "COMMENTARY", "SUSPENSE", "EXPLAIN", "RECAP", "FAIL", "JOKE"):
                idea = idea_sentence(new=rng.random() < traits["novelty"])
                sents.append(_render(L.IDEAS[idea["kind"]][idea["variant"]], idea["slots"]))
                novelty = max(novelty, 0.8) if idea is ideas[-1] else novelty
            else:
                pool = L.EVENTS["COMMENTARY"] if event in ("EXPLAIN", "RECAP") else L.EVENTS.get(event, L.EVENTS["COMMENTARY"])
                sents.append(_render(rnd.choice(pool), sv))
            words = _count_words(" ".join(sents))
        text = " ".join(sents)
        return text, novelty, repetition, True

    def add_fillers(text: str) -> tuple[str, float]:
        if traits["filler"] <= 0.02:
            return text, 0.0
        toks, out, n_fill = text.split(), [], 0
        for tok in toks:
            out.append(tok)
            if rng.random() < traits["filler"] * 0.09:
                out.append(rnd.choice(L.FILLERS) + ",")
                n_fill += 1
        return " ".join(out), n_fill / max(len(out), 1)

    def energize(text: str) -> str:
        if not energetic:
            return text
        if rng.random() < 0.45:
            text = rnd.choice(L.INTERJECTIONS) + " " + text
        return text.replace(". ", "! ") if rng.random() < 0.5 else text

    lo, hi = arch.cue_seconds
    while t < duration_target:
        # ---- choose the event ------------------------------------------------------------------------
        if not cues:
            event = "HOOK" if traits["hook_strength"] >= 0.45 else "INTRO_FLUFF"
        elif t < traits["intro_length"]:
            event = "HOOK" if (len(cues) == 1 and traits["hook_strength"] > 0.75) else (
                "INTRO_FLUFF" if rng.random() < (1 - 0.5 * traits["hook_strength"]) else "COMMENTARY")
        elif sponsor and sponsor_start <= t < sponsor_start + sponsor_len:
            event = "SPONSOR"
        elif not cta_done and t >= cta_time:
            event, cta_done = "CTA", True
        elif t >= next_payoff:
            event = "PAYOFF"
            first_payoff_done = True
            next_payoff = t + 60.0 / traits["payoff_rate"] * rng.uniform(0.6, 1.4)
        elif t > duration_target - 22:
            event = "OUTRO" if (cues[-1]["event"] != "OUTRO") else "CTA"
        else:
            r = rng.random()
            if r < traits["topic_shift"] * 0.12:
                event = "TOPIC_SHIFT"
            elif r < traits["topic_shift"] * 0.12 + traits["filler"] * 0.10:
                event = "FILLER"
            else:
                w = dict(arch.mix)
                near_payoff = 0 <= next_payoff - t <= 45
                w["SUSPENSE"] = w.get("SUSPENSE", .02) * (0.4 + 1.6 * traits["suspense"]) * (2.0 if near_payoff else 1.0)
                w["EXPLAIN"] = w.get("EXPLAIN", .05) * (0.4 + 1.6 * traits["information_density"])
                names = list(w)
                event = rnd.choices(names, weights=[w[n] for n in names])[0]
                if event != "SUSPENSE" and rng.random() < traits["repetition"] * 0.35 and len(ideas) >= 2:
                    event = "RECAP"

        if event == "TOPIC_SHIFT":
            slots.resample()

        # ---- render ------------------------------------------------------------------------------------
        cue_secs = float(rng.uniform(lo, hi))
        if event in ("HOOK", "OUTRO"):
            cue_secs = float(rng.uniform(5, 9))
        text, novelty, repetition, _ = compose(event, cue_secs * wps)
        text, filler_frac = add_fillers(energize(text))
        if event == "FILLER":
            filler_frac = max(filler_frac, 0.5)
        words = _count_words(text)
        dur = max(2.0, words / wps * float(rng.uniform(0.95, 1.05)))
        start, end = t, t + dur
        emotion = clip(EVENT_EMOTION.get(event, .15) * (0.35 + 0.65 * traits["emotional_intensity"]) + rng.normal(0, .05), 0, 1)
        susp = clip((0.9 if event == "SUSPENSE" else 0.1) * (0.4 + 0.6 * traits["suspense"]), 0, 1)
        sid = len(cues)
        cues.append(dict(segment_id=sid, start_time=round(start, 2), end_time=round(end, 2), text=text, event=event))
        latents.append(CueLatent(sid, event, round(novelty, 3), round(repetition, 3), round(filler_frac, 3), round(emotion, 3), round(susp, 3), words))
        t = end

    sv = slots.snapshot()
    title = rnd.choice(L.TITLES[archetype]).format(game=game, enemy=sv["enemy"], item=sv["item"], mech=sv["mech"], place=sv["place"], n=rnd.randint(2, 12))
    description = (f"In this video I play {game} ({L.GAMES[game]['sub']}). We take on {sv['enemy']} in {sv['place']} and look at the {sv['mech']}. "
                   f"#gaming #{game.split(':')[0].replace(' ', '').lower()}")
    meta = dict(video_id=video_id, title=title, description=description, duration=round(t, 2), genre="Gaming", subgenre=L.GAMES[game]["sub"],
                category="Gaming", game=game, language="en")
    gen_info = dict(archetype=archetype, family_idx=family_idx, template_family_id=f"{archetype}:{family_idx}",
                    traits={k: round(v, 4) for k, v in traits.items()}, sponsor=dict(present=sponsor, start=round(sponsor_start, 1), length=round(sponsor_len, 1)),
                    cta_mode=cta_mode, energetic=energetic, first_payoff_time=traits["payoff_latency"], seed=seed)
    return meta, cues, latents, gen_info
