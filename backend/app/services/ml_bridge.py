"""Bridge between the FastAPI app and the RetainAI ML engine (repo-root `src/` package).

The web app never imports the ML libraries (torch, sentence-transformers, xgboost, shap) at start-up. A background
thread loads the saved artifact once; until it is ready `status()` reports "loading" and predictions return a
controlled 503. If the artifact or dependencies are missing the service reports "unavailable" (and /api/ml/predict
returns 501), so the rest of the application is unaffected.
"""
import json
import logging
import sys
import threading
from pathlib import Path

from app.errors import AppError

logger = logging.getLogger("retention.ml")
ROOT = Path(__file__).resolve().parents[3]  # <repo>/backend/app/services/ml_bridge.py -> <repo>
DEFAULT_MODEL_DIR = ROOT / "models" / "retention_model_v1"
MODEL_DIR = DEFAULT_MODEL_DIR  # switched to the registry's production artifact by set_model_dir()

_state = {"state": "not_started", "error": None, "predictor": None, "meta": None}
_lock = threading.Lock()


def _ensure_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def set_model_dir(path) -> None:
    """Point inference at another artifact (registry promotion / rollback) and reload it in the background."""
    global MODEL_DIR
    MODEL_DIR = Path(path)
    with _lock:
        _state.update(state="not_started", error=None, predictor=None, meta=None)
    start_loading()


def artifact_meta() -> dict | None:
    p = MODEL_DIR / "metadata.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def _load() -> None:
    try:
        _ensure_path()
        from src.inference.pipeline import RetentionPredictor

        from src.features import schema

        meta = artifact_meta() or {}
        if meta.get("feature_schema_version") != schema.FEATURE_SCHEMA_VERSION:  # never run an incompatible feature pipeline
            raise RuntimeError(f"feature schema mismatch: model={meta.get('feature_schema_version')} pipeline={schema.FEATURE_SCHEMA_VERSION}")
        pred = RetentionPredictor.load(MODEL_DIR)
        with _lock:
            _state.update(state="ready", predictor=pred, meta=pred.meta, error=None)
        logger.info("ML model loaded: %s %s", pred.meta["model_name"], pred.meta["model_version"])
    except Exception as exc:  # noqa: BLE001 - any failure must degrade gracefully, never crash the app
        logger.warning("ML model unavailable: %s", type(exc).__name__)
        with _lock:
            _state.update(state="unavailable", error=f"{type(exc).__name__}: {str(exc)[:200]}")


def start_loading() -> None:
    """Idempotent. Called from the app lifespan; returns immediately."""
    with _lock:
        if _state["state"] != "not_started":
            return
        if artifact_meta() is None:
            _state.update(state="unavailable", error="no trained model artifact found (models/retention_model_v1)")
            return
        _state["state"] = "loading"
    threading.Thread(target=_load, name="ml-loader", daemon=True).start()


def status() -> dict:
    meta = artifact_meta() or {}
    with _lock:
        st, err = _state["state"], _state["error"]
    return {
        "model_available": st == "ready",
        "state": st,
        "model_name": meta.get("model_name"),
        "model_version": meta.get("model_version"),
        "feature_schema_version": meta.get("feature_schema_version"),
        "dataset_version": meta.get("dataset_version"),
        "trained_on": meta.get("trained_on"),
        "training_samples": meta.get("training_samples"),
        "synthetic_samples": meta.get("synthetic_samples"),
        "real_samples": meta.get("real_samples", 0),
        "last_trained": meta.get("training_date"),
        "embedding_model": meta.get("embedding_model"),
        "segment_seconds": meta.get("segment_seconds"),
        "real_validation_available": bool(meta.get("real_validation_available", False)),
        "message": ("Model trained on SYNTHETIC data; not validated on real YouTube retention." if "synthetic" in str(meta.get("trained_on")) and st == "ready"
                    else "ML model not connected." if st != "loading" else "ML model is loading…"),
        "error": err if st == "unavailable" else None,
    }


def get_predictor():
    with _lock:
        st, pred = _state["state"], _state["predictor"]
    if st == "ready":
        return pred
    if st == "loading":
        raise AppError("ML_LOADING", "The ML model is still loading. Please retry in a minute.", 503)
    raise AppError("ML_NOT_IMPLEMENTED", "The ML prediction pipeline is not connected yet.", 501)


# ---------------------------------------------------------------------------- synthetic demo data (held-out videos only)
def _demo_assign() -> dict:
    _ensure_path()
    import pandas as pd

    from src import config
    from src.training.splits import family_splits

    manifest = pd.read_csv(config.synthetic_dir() / "manifest.csv")
    seed = (artifact_meta() or {}).get("seed", config.SEED)
    return family_splits(manifest, int(seed)), manifest


def demo_videos(limit: int = 60) -> list[dict]:
    """Held-out (validation/test) synthetic videos the model was NOT trained on. Empty if the dataset isn't present."""
    try:
        assign, manifest = _demo_assign()
    except Exception:  # noqa: BLE001
        return []
    rows = manifest[manifest.video_id.map(assign).isin(["test"])]
    return [dict(video_id=r.video_id, title=r.title, archetype=r.archetype, duration_seconds=float(r.duration), split="test") for r in rows.itertuples()][:limit]


def demo_video(video_id: str) -> dict:
    _ensure_path()
    import numpy as np

    from src.data_generation.stats import load_raw_video, load_retention

    try:
        assign, _ = _demo_assign()
    except Exception:  # noqa: BLE001
        raise AppError("DEMO_DATA_UNAVAILABLE", "The synthetic demo dataset isn't available on this server.", 404)
    if assign.get(video_id) != "test":
        raise AppError("DEMO_VIDEO_NOT_FOUND", "That synthetic demo video isn't available (only held-out test videos are shown).", 404)
    raw = load_raw_video(video_id)
    values = np.asarray(load_retention()[video_id]["values"], dtype=float)
    ratios = np.linspace(0, 1, 101)
    target = [dict(time_ratio=float(r), retention=float(np.interp(r * (len(values) - 1), np.arange(len(values)), values))) for r in ratios]
    return dict(
        video_id=video_id, title=raw["title"], description=raw["description"], duration_seconds=raw["duration"], genre=raw["genre"],
        game=raw.get("game"), data_mode="synthetic", label="DEVELOPMENT / SYNTHETIC DATA",
        transcript=dict(segments=[dict(segment_id=s["segment_id"], start=s["start_time"], end=s["end_time"], text=s["text"]) for s in raw["segments"]]),
        synthetic_target=target,
    )


def reset_for_tests() -> None:
    with _lock:
        _state.update(state="not_started", error=None, predictor=None, meta=None)
