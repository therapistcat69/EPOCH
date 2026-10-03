"""Experiment runner. Every run records model_name, model_version, dataset_version, feature_schema_version,
segment_size, random_seed, training_date and validation/test metrics to experiments/results.jsonl.

Protocol: hyper-parameters are chosen on the VALIDATION split only; the test split is evaluated once per final
configuration; the risk threshold tau comes from TRAIN and the predicted-risk threshold from VALIDATION.
"""
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

DEEP_EPOCHS = 15  # hackathon budget: capped training length (early stopping still applies)
from src import config
from src.evaluation import evaluate as E
from src.evaluation import metrics as M
from src.models import baselines
from src.models.flat_models import FlatRetentionModel, stack_embeddings  # (torch-based models are imported lazily)
from src.training.dataset import build_dataset
from src.training.splits import assert_no_leakage, family_splits, split_frame

RESULTS = config.EXPERIMENTS_DIR / "results.jsonl"


def reconstruct_from_drops(df: pd.DataFrame, drops: np.ndarray) -> np.ndarray:
    """delta-target models: R_0 = 100, R_i = 100 - sum_{j<i} drop_j (clipped to [0, 100])."""
    out = np.zeros(len(df))
    pos = 0
    for _, g in df.groupby("video_id", sort=False):
        d = np.asarray(drops[pos : pos + len(g)], float)
        r = 100.0 - np.concatenate([[0.0], np.cumsum(d)[:-1]])
        out[pos : pos + len(g)] = np.clip(r, 0, 100)
        pos += len(g)
    return out


@dataclass
class Context:
    ds: dict
    df: pd.DataFrame
    assign: dict
    tr: pd.DataFrame
    va: pd.DataFrame
    te: pd.DataFrame
    tau: float
    segment_seconds: int
    embedder: str
    seed: int

    def emb(self, part: pd.DataFrame):
        return stack_embeddings(part, self.ds["embeddings"])

    def embs_for(self, part: pd.DataFrame) -> dict:
        ids = set(part.video_id)
        return {k: v for k, v in self.ds["embeddings"].items() if k in ids}


def make_context(segment_seconds: int = config.DEFAULT_SEGMENT_SECONDS, embedder_key: str = config.DEFAULT_EMBEDDING, seed: int = config.SEED) -> Context:
    """Loads the cached processed dataset (features + embeddings) - the embedding model is only loaded if it must be built."""
    import joblib

    from src.training.dataset import processed_path

    name = config.EMBEDDING_MODELS.get(embedder_key, embedder_key).split("/")[-1]
    path = processed_path(segment_seconds, name)
    if path.exists():
        ds = joblib.load(path)
    else:
        from src.embeddings import get_embedder

        ds = build_dataset(segment_seconds, get_embedder(embedder_key))
    manifest = pd.read_csv(config.synthetic_dir() / "manifest.csv")
    assign = family_splits(manifest, seed)
    assert_no_leakage(manifest, assign)  # hard stop if any video/family straddles splits
    df = ds["df"]
    tr, va, te = (split_frame(df, assign, s) for s in ("train", "val", "test"))
    assert not (set(tr.video_id) & set(te.video_id)) and not (set(tr.video_id) & set(va.video_id)) and not (set(va.video_id) & set(te.video_id))
    tau = M.risk_threshold_from_train(tr["drop_target"].to_numpy())
    means = M.position_means(tr["relative_position"].to_numpy(), tr["drop_target"].to_numpy())
    tau_ex = M.risk_threshold_from_train(tr["drop_target"].to_numpy() - M.position_lookup(means, tr["relative_position"].to_numpy()))
    ctx = Context(ds, df, assign, tr, va, te, tau, segment_seconds, ds["embedder"], seed)
    ctx.excess_means, ctx.excess_tau = means, tau_ex
    return ctx


def log_result(rec: dict) -> dict:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=float) + "\n")
    return rec


def _score(ctx: Context, name: str, pred_va, pred_te, risk_va=None, risk_te=None, features: str = "", extra: dict | None = None,
           model_version: str = config.MODEL_VERSION, experiment: str = "") -> dict:
    ex = dict(means=ctx.excess_means, tau=ctx.excess_tau, thr=None)
    va = E.evaluate_split(ctx.va, pred_va, risk_va, ctx.tau, None, ex)
    thr = M.best_threshold_f1(va["_scores"], va["_labels"])  # predicted-risk thresholds chosen on VALIDATION only
    ex["thr"] = M.best_threshold_f1(va["_ex_scores"], va["_ex_labels"])
    va = E.evaluate_split(ctx.va, pred_va, risk_va, ctx.tau, thr, ex)
    te = E.evaluate_split(ctx.te, pred_te, risk_te, ctx.tau, thr, ex)
    rec = dict(experiment=experiment, model_name=name, model_version=model_version, features=features, dataset_version=config.DATASET_VERSION,
               data_mode=config.MODE_SYNTHETIC, feature_schema_version=config.FEATURE_SCHEMA_VERSION, segment_size=ctx.segment_seconds,
               embedding_model=ctx.embedder, random_seed=ctx.seed, training_date=datetime.now(timezone.utc).isoformat(timespec="seconds"),
               risk_tau=ctx.tau, risk_threshold=thr, risk_excess_tau=ctx.excess_tau, risk_excess_threshold=ex["thr"],
               val=E.strip_private(va), test=E.strip_private(te), **(extra or {}))
    return log_result(rec)


# ------------------------------------------------------------------ model runners
def run_baselines(ctx: Context, experiment: str = "baselines") -> list[dict]:
    out = []
    y = ctx.tr["retention_target"].to_numpy()
    for cls in baselines.BASELINES:
        m = cls().fit(ctx.tr, y)
        out.append(_score(ctx, m.name, m.predict(ctx.va), m.predict(ctx.te), features="relative_position", experiment=experiment, model_version="naive"))
    return out


def run_flat(ctx: Context, kind: str, feature_sets: tuple, grid: list[dict], target: str = "retention_target", experiment: str = "", tag: str = "") -> dict:
    """Pick the best grid point by validation MAE, then evaluate val+test once with it."""
    best, best_mae, best_model, best_params = None, 1e9, None, None
    for params in grid:
        t0 = time.time()
        m = FlatRetentionModel(kind, feature_sets, ctx.seed, params, target)
        emb_tr = ctx.emb(ctx.tr) if "emb" in feature_sets else None
        emb_va = ctx.emb(ctx.va) if "emb" in feature_sets else None
        m.fit(ctx.tr, emb_tr, ctx.va, emb_va)
        pv = m.predict(ctx.va, emb_va)
        if target == "drop_target":
            pv = reconstruct_from_drops(ctx.va, pv)
        mae = float(np.abs(pv - ctx.va["retention_target"].to_numpy())[ctx.va.segment_id.to_numpy() > 0].mean())
        if mae < best_mae:
            best, best_mae, best_model, best_params, fit_s = pv, mae, m, params, time.time() - t0
    m = best_model
    emb_va = ctx.emb(ctx.va) if "emb" in feature_sets else None
    emb_te = ctx.emb(ctx.te) if "emb" in feature_sets else None
    t0 = time.time()
    raw_te = m.predict(ctx.te, emb_te)
    latency = (time.time() - t0) / max(ctx.te.video_id.nunique(), 1)
    raw_va = m.predict(ctx.va, emb_va)
    if target == "drop_target":
        pred_va, pred_te = reconstruct_from_drops(ctx.va, raw_va), reconstruct_from_drops(ctx.te, raw_te)
        risk_va, risk_te = np.maximum(raw_va, 0), np.maximum(raw_te, 0)
    else:
        pred_va, pred_te, risk_va, risk_te = raw_va, raw_te, None, None
    name = f"{kind}{'_delta' if target == 'drop_target' else ''}{tag}"
    rec = _score(ctx, name, pred_va, pred_te, risk_va, risk_te, features="+".join(feature_sets), experiment=experiment,
                 extra=dict(best_params=best_params, inference_seconds_per_video=latency, n_features=len(m.feature_names()) if m.model is not None else None))
    rec["_model"] = m
    return rec


def fit_deep(ctx: Context, arch: str, use_embedding: bool, cfg: dict, seed: int | None, epochs: int):
    from src.models.deep_models import DeepRetentionModel

    m = DeepRetentionModel(arch, use_embedding, seed if seed is not None else ctx.seed, dict(cfg))
    t0 = time.time()
    m.fit(ctx.tr, ctx.embs_for(ctx.tr), ctx.va, ctx.embs_for(ctx.va), epochs=epochs)
    return m, time.time() - t0


def run_deep_grid(ctx: Context, arch: str, grid: list[dict], use_embedding: bool = True, experiment: str = "", tag: str = "", epochs: int = DEEP_EPOCHS,
                  seed: int | None = None) -> dict:
    """Train every config, select by VALIDATION MAE only, evaluate test once for the selected config."""
    cands = []
    for cfg in grid:
        m, fit_s = fit_deep(ctx, arch, use_embedding, cfg, seed, epochs)
        cands.append((m.best_val_mae, cfg, m, fit_s))
    cands.sort(key=lambda c: c[0])
    best_mae, cfg, m, fit_s = cands[0]
    grid_summary = [dict(config=c[1], val_mae=round(c[0], 3)) for c in cands]
    return score_deep(ctx, m, fit_s, use_embedding, cfg, experiment, tag, grid_summary)


def run_deep(ctx: Context, arch: str, use_embedding: bool = True, cfg: dict | None = None, experiment: str = "", tag: str = "", epochs: int = DEEP_EPOCHS,
             seed: int | None = None) -> dict:
    m, fit_s = fit_deep(ctx, arch, use_embedding, dict(cfg or {}), seed, epochs)
    return score_deep(ctx, m, fit_s, use_embedding, dict(cfg or {}), experiment, tag, None)


def score_deep(ctx: Context, m, fit_s: float, use_embedding: bool, cfg: dict, experiment: str, tag: str, grid_summary) -> dict:
    t1 = time.time()
    pte = m.predict_videos(ctx.te, ctx.embs_for(ctx.te))
    latency = (time.time() - t1) / max(len(pte), 1)
    pva = m.predict_videos(ctx.va, ctx.embs_for(ctx.va))

    def flat(part, pred):
        ret = np.concatenate([pred[v][0] for v in part.video_id.unique()])
        risk = np.concatenate([pred[v][1] for v in part.video_id.unique()]) if pred[next(iter(pred))][1] is not None else None
        return ret, (np.maximum(risk, 0) if risk is not None else None)

    rv, kv = flat(ctx.va, pva)
    rt, kt = flat(ctx.te, pte)
    rec = _score(ctx, m.name + tag, rv, rt, kv, kt, features="hand+emb" if use_embedding else "hand", experiment=experiment,
                 extra=dict(n_params=m.n_params(), epochs_run=len(m.history), best_val_mae=m.best_val_mae, fit_seconds=fit_s,
                            inference_seconds_per_video=latency, config=cfg, grid=grid_summary,
                            train_val_gap=dict(first_train_loss=m.history[0]["train_loss"], last_train_loss=m.history[-1]["train_loss"])))
    rec["_model"], rec["_history"] = m, m.history
    return rec


def summarize(rec: dict) -> str:
    t = rec["test"]
    ex = t["risk_excess"]
    return (f"{rec['model_name']:<30} {rec['features']:<14} seg={rec['segment_size']:>2}s  val_MAE={rec['val']['regression']['mae']:6.2f}  "
            f"test: MAE={t['regression']['mae']:6.2f} RMSE={t['regression']['rmse']:6.2f} R2={t['regression']['r2']:6.3f} "
            f"r={t['regression']['pearson']:6.3f} | risk(abs) top3={t['risk']['top3_hit']:.2f} (chance {t['risk']['chance_top3']:.2f}) lift={t['risk']['precision_lift']:.2f}"
            f" | risk(excess) top3={ex['top3_hit']:.2f} (chance {ex['chance_top3']:.2f}) lift={ex['precision_lift']:.2f} rec={ex['risk_recall']:.2f}")
