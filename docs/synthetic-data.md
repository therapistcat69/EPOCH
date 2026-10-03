# Synthetic data (`synthetic_v1`)

> **Synthetic data is used for model development and integration testing and must not be interpreted as real YouTube audience behavior.**

Any model trained on it demonstrates a *pipeline*. A low error on synthetic data is **not** evidence of real-world accuracy: the model may simply have learned the generator (see "Limitations").

Everything here is reproducible: `python -m src.data_generation.generate --seed 42` regenerates the identical dataset (a test asserts byte-identical output for the same seed and different output for a different seed).

## What is generated

| Item | Value |
| --- | --- |
| Videos | **420** (10 archetypes × 6 template families × 7 videos) |
| Duration | 603–905 s (10–15 minutes), mean ≈ 753 s |
| Domain | Gaming (12 real game vocabularies: Elden Ring, Minecraft, Fortnite, Valorant, GTA Online, …) |
| Transcript granularity | caption cues (~4–11 s each, ≈ 37 000 cues, ≈ 76 % distinct cue texts); aggregated later to 10/15/20/30 s segments by the segmentation module |
| Labels | retention curve R(t) in percent on a 1-second grid (`data/synthetic/synthetic_v1/retention.json`) |
| Seed | 42 (global); per-video generator is seeded with `[seed, archetype, family, index]` |
| Dataset version | `synthetic_v1` (`config.DATASET_VERSION`); feature schema `1.0` |

Files (every file is tagged `data_mode: "synthetic"`; real data lives separately in `data/real/` and is never mixed):

```
data/raw/synthetic_v1/videos/<video_id>.json      video_id, title, description, duration, genre, subgenre, segments[{segment_id,start_time,end_time,text}]
data/synthetic/synthetic_v1/retention.json         synthetic retention labels
data/synthetic/synthetic_v1/generator_meta.jsonl   latent traits + per-cue events  (generator-internal, NEVER used as model input)
data/synthetic/synthetic_v1/manifest.csv           video_id, archetype, family, template_family_id, duration, ...
data/processed/synthetic_v1/seg<N>_<embedder>.joblib  features + cached embeddings (built by src.training.build_all)
```

## Archetypes

`fast_challenge`, `gameplay_commentary`, `story_driven`, `tutorial_guide`, `reaction`, `tournament_highlights`, `boss_fight`, `funny_montage`, `strategy_explanation`, `review_style` (`src/data_generation/archetypes.py`). Each archetype is a prior over the latent traits below plus a mix over content events.

## Generation process

1. **Latent traits** are sampled per video: `hook_strength`, `intro_length`, `pacing` (→ 110–210 words/minute), `information_density`, `repetition`, `novelty`, `topic_shift`, `suspense`, `emotional_intensity`, `payoff_latency`, `payoff_rate`, sponsor presence/intrusiveness, `filler`, `energetic`. Trait = archetype mean + a fixed **per-family offset** + per-video noise.
2. **Event timeline** (state machine): HOOK/INTRO_FLUFF during the intro, a forced PAYOFF at `payoff_latency` and then at `payoff_rate`, SPONSOR block (if present), CTA (early / mid / end / none), OUTRO, and content events (GAMEPLAY_ACTION, COMMENTARY, SUSPENSE, FAIL, JOKE, EXPLAIN, RECAP, TOPIC_SHIFT, FILLER) drawn from the archetype mix, modulated by the traits (e.g. suspense weight rises before a payoff; `repetition` converts cues into RECAPs).
3. **Text** is rendered from template banks with slot filling (game-specific enemies, items, places, mechanics). Ideas (strategy / fact / route / opinion / stat) have three wordings with shared content words, so a RECAP restates an earlier idea in *different words* (the case semantic repetition features must catch). Fillers and interjections follow the traits; one-off lines (intro, outro, sponsor, CTA) are never repeated within a video. Speaking speed sets how long each cue lasts, so measured words-per-minute is consistent with `pacing`.
4. **Retention** is simulated from the per-cue latent record (below). Latent event labels are stored only in `generator_meta.jsonl`; the raw transcript contains nothing but id, start, end and text.

## Retention generator (formula)

A survival-style process on a 1-second grid, with `S(t)` the fraction still watching and `R(t) = 100·S(t)`:

```
dS/dt = -h(t)·S(t) + b(t)·(1 - S(t))                  # hazard of leaving + small re-watch inflow
h(t)  = h_base(t) · m_hook(t) · m_delay(t) · m_cue(t) · m_topic(t) · exp(noise(t))

h_base(t) = h_inf + (h_0 - h_inf)·exp(-t/τ)           h_0 = 0.0060, h_inf = 0.00042, τ = 24 s   (steep early loss, slow late loss)
m_hook(t) = 1 + 1.0·(1 - hook_strength)·exp(-t/22)    weak opening → extra early drop-off
m_delay(t)= 1 + 0.7·clip((payoff_latency - 30)/60, 0, 1)   until the first payoff → delayed payoff raises risk
m_cue(t)  = product of per-cue multipliers (below)
m_topic(t)= 1 + 1.2·abruptness·exp(-(t - t_shift)/8)  after an abrupt TOPIC_SHIFT
noise(t)  = AR(1), φ = 0.92, σ = 0.18
```

Per-cue multiplier on `h` (≈ "baseline_decay + hook_effect + novelty_effect + repetition_penalty + payoff_effect + topic_transition_effect + suspense_effect + noise"):

| Event | base | | Modifier | Effect |
| --- | --- | --- | --- | --- |
| HOOK .65 · SUSPENSE .55 · PAYOFF .40 · GAMEPLAY .85 · JOKE .85 | stabilizing | | `× (1 + 0.9·repetition_cue)` | repeated explanations → local drop-off |
| COMMENTARY/EXPLAIN 1.0 · FAIL 1.1 · RECAP 1.15 · TOPIC_SHIFT 1.2 · CTA 1.15 | neutral/risky | | `× (1 + 0.8·(1 - novelty_cue))` | low novelty → local decline |
| INTRO_FLUFF 1.25 · SPONSOR 1.2 · OUTRO 1.3 · FILLER 1.5 | risky | | `× (1 + 0.7·filler_cue)` | filler words |
| | | | `× (1 + 1.5·intrusiveness)` (SPONSOR only) | configurable sponsor risk |
| | | | `÷ (1 + 0.5·emotion_cue)` | emotional/gameplay events stabilize |

**Monotonicity is not enforced.** After PAYOFF cues and high-emotion moments a short re-watch inflow `b(t)` (up to ≈ 1.2 percentage points) is allowed, justified as "replay-worthy moment / major payoff / exciting event", because real retention metrics can rise through re-watches. Observation noise (σ = 0.08) and a 5-second moving average are applied; the result is clipped to [0, 100] and `R(0) = 100`.

These relationships are **generator assumptions**, not claims about real YouTube causality (tests assert they hold inside the generator: stronger hook → higher retention at 30 s; later payoff → lower mid-video retention).

### Observed properties of `synthetic_v1`

| Property | Value |
| --- | --- |
| Final retention | 27–75 %, mean ≈ 50 % (by archetype: tournament highlights/fast challenge ≈ 63–65 %, review/strategy ≈ 35 %) |
| Mean loss in the first 30 s | ≈ 22 % |
| Fraction of seconds with a rise | ≈ 2 % |
| Strictly monotone videos | 0 / 420 |

**Honest note on calibration:** a first version of the simulator (h_0 = 0.0115) produced a ≈ 42 % loss in the first 30 s and noisy curves (26 % of seconds rising). Both were implausible and were corrected after inspecting these statistics (h_0 → 0.0060, smoothing 3 s → 5 s). Two generator bugs found while inspecting transcripts were also fixed: intro lines repeating inside a video, and the "re-use an earlier line" branch placing intro text inside gameplay cues. The constants remain *assumptions*; they were adjusted for plausibility, not fit to real data.

## Segmentation

Default 15 s, configurable (`segment_duration_seconds`; experiments use 10 / 15 / 20 / 30 s). Cues are split **word-wise** across the windows they overlap; original timestamps, raw text and cleaned text are all preserved. Empty windows (no captions) are kept. Position features `absolute_time` and `relative_position = segment_start / duration` are attached to every segment.

## Train / validation / test split (no leakage)

* Unit of separation = the **template family** (archetype + fixed trait offsets), not just the video. Per archetype: 4 families → train, 1 → validation, 1 → test (≈ 67 % / 17 % / 17 % of videos; 280 / 70 / 70).
* Validation and test therefore contain *unseen combinations* of hook strength, pacing, repetition, topic structure and payoff timing — a test of generalization rather than memorization of generator templates.
* Segments of a video never cross splits. `assert_no_leakage` (and the test-suite) fail if any video or family appears in two splits.
* `GroupKFold(group=video_id)` is provided for cross-validation on the training set.
* The risk threshold τ is derived from **training** videos only; the predicted-risk threshold is chosen on **validation** only.

## Limitations (read before trusting any number)

1. **The model can learn the generator.** Retention is a deterministic-plus-noise function of latent traits that are expressed in the text; features such as repetition and novelty are *designed* to correlate with those latents. High accuracy on synthetic data mostly measures how well the model inverts the generator.
2. **Template language.** Text comes from ≈ 100 templates; real transcripts are far more varied (ASR errors, slang, multilingual speech, music).
3. **One domain, English only.** Gaming-focused; Hindi/Hinglish are not represented in the synthetic data.
4. **No real confounders.** Real retention depends on the channel, audience, thumbnail/title, traffic source, video length, topic popularity and chance; none of that is simulated.
5. **Synthetic-generator bias.** Direction and size of every effect were chosen by us; real effect sizes may differ or even reverse.
6. **Held-out ≠ independent.** Test videos come from the same generator, so even family hold-out measures generalization only *within* the generator's world.
