"""Small, dependency-free NLP toolkit: tokenization, TF-IDF, cosine similarity, clustering.

Deterministic and reproducible. Works on any Unicode script (English, Devanagari/Hindi, Hinglish).
The Groq API has no embeddings endpoint, so semantic similarity here is lexical (TF-IDF cosine);
swap `vectorize`/`cosine` for an embedding model later without touching callers.
"""
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_URL_RE = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+", re.I)

STOPWORDS = frozenset(
    """https http www com org net html youtube youtu watch subscribe channel video videos official free new today now
    shorts short ytshorts shortsfeed viral trending fyp
    a an the and or but if then so of to in on at by for with from as is are was were be been being it its this that
    these those i you he she we they me my your our their them his her do does did done have has had will would can could
    should may might just not no yes very really also about into over than too out up down all any more most some such
    what which who whom when where why how there here get got let lets like one two im ive youre dont thats
    hai hain ho hoga hogi tha thi the ka ki ke ko se me mein par pe aur ya to toh ye yeh wo woh kya kyun kyu kaise nahi nahin
    hum tum aap mai main mera meri mere tera teri apna apni apne kuch bhi hi na ek bahut abhi jab tab agar lekin
    है हैं का की के को से में पर और या यह वह क्या कैसे नहीं हम तुम आप मैं एक भी ही""".split()
)


def strip_urls(text: str) -> str:
    return _URL_RE.sub(" ", text or "")


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    toks = [t.lower() for t in _TOKEN_RE.findall(strip_urls(text))]
    return toks if keep_stopwords else [t for t in toks if t not in STOPWORDS and len(t) > 1 and not t.isdigit()]


def word_count(text: str) -> int:
    return len(_TOKEN_RE.findall(text or ""))


Vector = dict[str, float]


def build_idf(docs: list[list[str]]) -> dict[str, float]:
    n = len(docs)
    df: Counter[str] = Counter()
    for d in docs:
        df.update(set(d))
    return {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}


def vectorize(tokens: list[str], idf: dict[str, float]) -> Vector:
    tf = Counter(tokens)
    if not tf:
        return {}
    vec = {t: (1 + math.log(c)) * idf.get(t, 1.0) for t, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in vec.values()))
    return {t: v / norm for t, v in vec.items()} if norm else {}


def cosine(a: Vector, b: Vector) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def cluster(vectors: list[Vector], threshold: float = 0.3) -> list[list[int]]:
    """Greedy centroid clustering (single pass, then one reassignment pass). Returns lists of indices."""
    centroids: list[Vector] = []
    members: list[list[int]] = []

    def add(i: int) -> None:
        best, best_sim = -1, threshold
        for ci, c in enumerate(centroids):
            s = cosine(vectors[i], c)
            if s >= best_sim:
                best, best_sim = ci, s
        if best == -1:
            centroids.append(dict(vectors[i]))
            members.append([i])
        else:
            members[best].append(i)
            c = centroids[best]
            for t, v in vectors[i].items():
                c[t] = c.get(t, 0.0) + v

    for i in range(len(vectors)):
        add(i)
    # one refinement pass with the final centroids
    norm = [{t: v / (math.sqrt(sum(x * x for x in c.values())) or 1) for t, v in c.items()} for c in centroids]
    groups: dict[int, list[int]] = {}
    for i, v in enumerate(vectors):
        sims = [cosine(v, c) for c in norm]
        best = max(range(len(norm)), key=lambda k: sims[k]) if norm else 0
        groups.setdefault(best, []).append(i)
    return [g for g in groups.values() if g]


def top_terms(token_lists: list[list[str]], k: int = 3) -> list[str]:
    """Most distinctive frequent terms across a group (document frequency, ties by total count)."""
    df: Counter[str] = Counter()
    tf: Counter[str] = Counter()
    for toks in token_lists:
        df.update(set(toks))
        tf.update(toks)
    ranked = sorted(df, key=lambda t: (-df[t], -tf[t], t))
    return ranked[:k]


def leading_ngram(title: str, n: int) -> str | None:
    toks = [t.lower() for t in _TOKEN_RE.findall(title or "")]
    return " ".join(toks[:n]) if len(toks) >= n else None


def median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return float(vals[mid]) if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None
