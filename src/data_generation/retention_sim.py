"""Synthetic audience-retention simulator (transparent, reproducible).

THESE ARE GENERATOR ASSUMPTIONS, NOT CLAIMS ABOUT REAL YOUTUBE CAUSALITY.

Retention is a survival-style process on a 1-second grid. With S(t) in [0, 1] the fraction still watching and
R(t) = 100 * S(t):

    dS/dt = -h(t) * S(t)  +  b(t) * (1 - S(t))                      (hazard of leaving  +  small re-watch inflow)

    h(t)  = h_base(t) * m_hook(t) * m_delay(t) * m_cue(t) * m_topic(t) * exp(noise(t))

    h_base(t) = h_inf + (h_0 - h_inf) * exp(-t / tau)                (steep early loss, slow late loss)
    m_hook(t) = 1 + A_h * (1 - hook_strength) * exp(-t / tau_h)      (weak opening -> extra early drop-off)
    m_delay(t)= 1 + A_d * clip((payoff_latency - 30) / 60, 0, 1)     for t < first payoff (delayed payoff -> risk)
    m_cue(t)  = product of the per-cue multipliers below
    m_topic(t)= 1 + A_t * abruptness * exp(-(t - t_shift) / tau_t)   after an abrupt TOPIC_SHIFT cue
    noise(t)  = AR(1) process (phi = 0.92, sigma = 0.22)

Per-cue multiplier on h (all > 0; < 1 stabilizes retention, > 1 increases drop-off):
    event base:  HOOK .65  GAMEPLAY_ACTION .85  COMMENTARY 1.0  SUSPENSE .55  PAYOFF .40  FAIL 1.1  JOKE .85
                 EXPLAIN 1.0  RECAP 1.15  FILLER 1.5  INTRO_FLUFF 1.25  SPONSOR 1.2  CTA 1.15  OUTRO 1.3  TOPIC_SHIFT 1.2
    x (1 + 0.9 * repetition_cue)            repeated explanations -> local drop-off
    x (1 + 0.8 * (1 - novelty_cue))         low novelty -> local decline
    x (1 + 0.7 * filler_cue)                filler words
    x (1 + 1.5 * intrusiveness)             for SPONSOR cues (configurable risk pattern)
    / (1 + 0.5 * emotion_cue)               emotional / exciting moments stabilize
    suspense cues before a payoff slow the decline (event base .55 above); the PAYOFF cue stabilizes it (.40)

Re-watch inflow b(t): after PAYOFF / high-emotion cues a short bump of up to ~1.2 percentage points is allowed
(replay-worthy moments), so the curve is NOT forced to be monotone - consistent with real retention metrics, which
can rise because of rewatches.

Observation noise: small Gaussian measurement noise + 3 s moving average, then clipped to [0, 100], R(0) = 100.
"""
import numpy as np

EVENT_H = dict(HOOK=.65, GAMEPLAY_ACTION=.85, COMMENTARY=1.0, SUSPENSE=.55, PAYOFF=.40, FAIL=1.1, JOKE=.85, EXPLAIN=1.0,
               RECAP=1.15, FILLER=1.5, INTRO_FLUFF=1.25, SPONSOR=1.2, CTA=1.15, OUTRO=1.3, TOPIC_SHIFT=1.2)

# NOTE: a first version (H0=0.0115) produced a mean 42% loss in the first 30 s, which is implausibly steep, and
# ~26% of seconds with a rise (too noisy). Constants below were reduced after inspecting dataset statistics.
H0, H_INF, TAU = 0.0060, 0.00042, 24.0
A_HOOK, TAU_HOOK = 1.0, 22.0
A_DELAY = 0.7
A_TOPIC, TAU_TOPIC = 1.2, 8.0
AR_PHI, AR_SIGMA = 0.92, 0.18
OBS_NOISE = 0.08
BUMP_MAX = 1.2


def simulate_retention(cues: list[dict], latents: list, traits: dict, sponsor_intrusiveness: float, rng: np.random.Generator) -> np.ndarray:
    """Return R(t) in percent at 1-second resolution for t = 0..ceil(duration)."""
    duration = cues[-1]["end_time"]
    n = int(np.ceil(duration)) + 1
    t = np.arange(n, dtype=float)

    h = H_INF + (H0 - H_INF) * np.exp(-t / TAU)
    h = h * (1 + A_HOOK * (1 - traits["hook_strength"]) * np.exp(-t / TAU_HOOK))
    first_payoff = next((c["start_time"] for c in cues if c["event"] == "PAYOFF"), duration)
    delay = A_DELAY * np.clip((traits["payoff_latency"] - 30) / 60.0, 0, 1)
    h = h * np.where(t < first_payoff, 1 + delay, 1.0)

    cue_mult = np.ones(n)
    bump = np.zeros(n)
    topic = np.ones(n)
    for c, lat in zip(cues, latents):
        s, e = int(c["start_time"]), min(int(np.ceil(c["end_time"])), n)
        m = EVENT_H.get(lat.event, 1.0)
        m *= 1 + 0.9 * lat.repetition
        m *= 1 + 0.8 * (1 - lat.novelty)
        m *= 1 + 0.7 * lat.filler
        if lat.event == "SPONSOR":
            m *= 1 + 1.5 * sponsor_intrusiveness
        m /= 1 + 0.5 * lat.emotion
        cue_mult[s:e] = m
        if lat.event == "PAYOFF" or lat.emotion > 0.7:
            amp = BUMP_MAX * (0.4 + 0.6 * lat.emotion) * (1.0 if lat.event == "PAYOFF" else 0.5)
            b_end = min(s + 6, n)
            bump[s:b_end] += amp / 100.0 / 6.0 * 100.0 / 100.0  # spread over ~6 s (fraction of the lost audience returning)
        if lat.event == "TOPIC_SHIFT":
            abrupt = 0.6 + 0.4 * lat.novelty
            tail = np.arange(n - s)
            topic[s:] *= 1 + A_TOPIC * abrupt * np.exp(-tail / TAU_TOPIC)
    h = h * cue_mult * topic

    noise = np.zeros(n)
    eps = rng.normal(0, AR_SIGMA * np.sqrt(1 - AR_PHI**2), n)
    for i in range(1, n):
        noise[i] = AR_PHI * noise[i - 1] + eps[i]
    h = h * np.exp(noise)

    S = np.ones(n)
    for i in range(1, n):
        s_prev = S[i - 1]
        S[i] = s_prev - h[i] * s_prev + bump[i] * (1 - s_prev)
        S[i] = min(max(S[i], 0.0), 1.0)
    R = S * 100.0
    R = R + rng.normal(0, OBS_NOISE, n)
    k = 5
    R = np.convolve(np.pad(R, (k // 2, k // 2), mode="edge"), np.ones(k) / k, mode="valid")
    R[0] = 100.0
    return np.clip(R, 0.0, 100.0)
