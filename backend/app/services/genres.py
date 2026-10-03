"""Genre / subgenre catalogue: seed search queries per genre. Plain configuration, easy to extend."""

GENRES: dict[str, dict] = {
    "Technology": {
        "queries": ["technology", "tech review"],
        "subgenres": {"AI Tools": ["AI tools", "AI coding agents"], "Smartphones": ["smartphone review", "new smartphone"], "Gadgets": ["gadget review"]},
    },
    "AI": {
        "queries": ["artificial intelligence", "AI tutorial"],
        "subgenres": {"AI Coding Agents": ["AI coding agent", "Claude Code Cursor Codex"], "LLMs": ["large language model", "ChatGPT Claude Gemini"], "Generative AI": ["generative AI tools"]},
    },
    "Programming": {
        "queries": ["programming tutorial", "software engineering"],
        "subgenres": {"Web Development": ["web development tutorial", "React Next.js"], "DSA": ["data structures and algorithms", "leetcode"], "Python": ["python tutorial"]},
    },
    "Education": {
        "queries": ["education explained", "study tips"],
        "subgenres": {"Mathematics": ["mathematics explained", "math tutorial"], "Science": ["science explained"], "Exams": ["exam preparation"]},
    },
    "Gaming": {
        "queries": ["gaming", "gameplay"],
        "subgenres": {"Mobile Gaming": ["mobile gaming", "BGMI"], "PC Gaming": ["PC gaming"], "Game Reviews": ["game review"]},
    },
    "Finance": {
        "queries": ["personal finance", "investing"],
        "subgenres": {"Stock Market": ["stock market", "share market"], "Mutual Funds": ["mutual funds"], "Crypto": ["cryptocurrency"]},
    },
    "Fitness": {
        "queries": ["fitness workout", "gym"],
        "subgenres": {"Home Workouts": ["home workout"], "Nutrition": ["nutrition diet"], "Weight Loss": ["weight loss"]},
    },
    "Vlogs": {
        "queries": ["vlog", "day in my life"],
        "subgenres": {"Travel Vlogs": ["travel vlog"], "Student Life": ["student life vlog"], "Daily Vlogs": ["daily vlog"]},
    },
    "Business": {
        "queries": ["business", "entrepreneurship"],
        "subgenres": {"Startups": ["startup"], "Marketing": ["digital marketing"], "Side Hustles": ["side hustle"]},
    },
    "Entertainment": {
        "queries": ["entertainment", "trending video"],
        "subgenres": {"Movies": ["movie review"], "Music": ["music video"], "Comedy": ["comedy sketch"]},
    },
}

TIME_WINDOWS = {"7d": 7, "30d": 30, "90d": 90}
LANGUAGES = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "mr": "Marathi"}
REGIONS = {"IN": "India", "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia"}


def catalogue() -> dict:
    return {
        "genres": [{"name": g, "subgenres": list(cfg["subgenres"])} for g, cfg in GENRES.items()],
        "languages": [{"code": c, "name": n} for c, n in LANGUAGES.items()],
        "regions": [{"code": c, "name": n} for c, n in REGIONS.items()],
        "time_windows": list(TIME_WINDOWS),
    }


def resolve(genre: str, subgenre: str | None) -> tuple[str, str | None, list[str]]:
    """Case-insensitive lookup. Returns (canonical genre, canonical subgenre, seed queries)."""
    key = next((g for g in GENRES if g.lower() == genre.lower()), None)
    if key is None:
        raise KeyError(genre)
    cfg = GENRES[key]
    if subgenre:
        sub = next((s for s in cfg["subgenres"] if s.lower() == subgenre.lower()), None)
        if sub is None:  # unknown subgenre: treat it as a free-text refinement of the genre
            return key, subgenre, [f"{subgenre} {cfg['queries'][0]}"]
        return key, sub, cfg["subgenres"][sub]
    return key, None, cfg["queries"]
