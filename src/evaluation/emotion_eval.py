"""Compare the lightweight emotion/sentiment scorers on a small, hand-written GAMING sentence set.

This is a deliberately small sanity check (not a benchmark): it measures whether the gaming lexicon and a general
sentiment model (VADER) agree with a human reading on gaming language. Results are written to
experiments/emotion_eval.json and quoted in the docs. Limitations are documented, not hidden.
"""
import json

from src import config
from src.features.emotion import lexicon_emotions, vader_sentiment

# (text, expected dominant emotion, expected sentiment sign)  - written by hand for the gaming domain
SET = [
    ("Yes! We finally did it, first try, let's go!", "excitement", "pos"),
    ("That clutch was insane, absolutely epic!", "excitement", "pos"),
    ("No way, I did not expect that to happen!", "surprise", "pos"),
    ("Wait, what? Where did that boss come from?", "surprise", "neu"),
    ("My health is almost gone and one wrong move ends the run.", "fear", "neg"),
    ("I am so scared, he is getting closer and I can barely move.", "fear", "neg"),
    ("That hit was so unfair, this is incredibly frustrating.", "anger", "neg"),
    ("Seriously? That is cheating, I hate this boss.", "anger", "neg"),
    ("I died again, back to the start, that really hurts.", "sadness", "neg"),
    ("Unfortunately we lost the match and I am sorry, guys.", "sadness", "neg"),
    ("I love this game, the map is beautiful and the music is amazing.", "joy", "pos"),
    ("This is so much fun, I am really enjoying this part.", "joy", "pos"),
    ("This boss is brutal but the fight feels so satisfying.", "joy", "pos"),
    ("The map has three zones and a river in the middle.", "none", "neu"),
    ("You can find the key in the second room on the left.", "none", "neu"),
    ("The patch changed the damage values for the shotgun.", "none", "neu"),
    ("OMG I cannot believe we actually won that, what a clutch!", "excitement", "pos"),
    ("Oh no, I fell off the map again, this is ridiculous.", "anger", "neg"),
    ("The enemy team is tense and panicking near the final circle.", "fear", "neg"),
    ("Honestly the story in this game made me really sad.", "sadness", "neg"),
]
EMOS = ["joy", "surprise", "fear", "anger", "sadness", "excitement"]


def evaluate() -> dict:
    lex_ok = lex_none_ok = vader_ok = vader_neu_ok = 0
    n_none = sum(1 for _, e, _ in SET if e == "none")
    n_emo = len(SET) - n_none
    detail = []
    for text, emo, sign in SET:
        scores = lexicon_emotions(text)
        top = max(EMOS, key=lambda e: scores[e])
        predicted = top if scores[top] > 0 else "none"
        v = vader_sentiment(text)["compound"]
        vs = "pos" if v >= 0.25 else "neg" if v <= -0.25 else "neu"
        if emo == "none":
            lex_none_ok += predicted == "none"
        else:
            lex_ok += predicted == emo
        vader_ok += vs == sign
        detail.append(dict(text=text, expected=emo, lexicon=predicted, expected_sign=sign, vader=vs, vader_compound=round(v, 3)))
    out = dict(
        n_sentences=len(SET),
        lexicon_emotion_accuracy_on_emotional_sentences=round(lex_ok / n_emo, 3),
        lexicon_correct_on_neutral_sentences=round(lex_none_ok / max(n_none, 1), 3),
        vader_sentiment_sign_accuracy=round(vader_ok / len(SET), 3),
        note="small hand-written gaming set (20 sentences); indicative only. VADER has no emotion categories (excitement/surprise/fear...), "
             "so only sentiment sign is compared. Both are lexical and miss sarcasm/context.",
        detail=detail,
    )
    (config.EXPERIMENTS_DIR).mkdir(parents=True, exist_ok=True)
    (config.EXPERIMENTS_DIR / "emotion_eval.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = evaluate()
    print({k: v for k, v in r.items() if k != "detail"})
    for d in r["detail"]:
        flag = "" if d["lexicon"] == d["expected"] else "  <-- lexicon miss"
        print(f"  {d['expected']:<10} lex={d['lexicon']:<10} vader={d['vader']:<4} {d['text'][:60]}{flag}")
