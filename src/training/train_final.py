"""Train and save the primary model (the one chosen by src.training.select_model) as a deployable artifact.

    python -m src.training.train_final            # reads experiments/selected_model.json

Artifact (models/retention_model_v1/):
    model.pkl | model.pt + scaler.pkl + net_config.json   model AND its preprocessing (TF-IDF / scaler / feature list)
    feature_config.json                                   feature groups, pre-publication list, target mode
    metadata.json                                         versions, data provenance, risk thresholds, metrics, uncertainty calibration
    ensemble/member_k/                                    members for ensemble-spread uncertainty
The model is trained on TRAIN with VALIDATION for early stopping; the test split is only used for the reported metrics.
"""
import json
import platform
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src import config
from src.evaluation import metrics as M
from src.features import schema
from src.models.deep_models import DeepRetentionModel
from src.models.flat_models import FlatRetentionModel
from src.training import experiments as X

ENSEMBLE_SEEDS = (11, 22, 33, 44, 55)


def train_member(ctx: X.Context, spec: dict, seed: int):
    if spec["kind"] == "flat":
        fs = tuple(spec["features"].split("+"))
        m = FlatRetentionModel(spec["family"], fs, seed, spec.get("params") or {}, spec["target"])
        emb_tr = ctx.emb(ctx.tr) if "emb" in fs else None
        emb_va = ctx.emb(ctx.va) if "emb" in fs else None
        m.fit(ctx.tr, emb_tr, ctx.va, emb_va)
        return m
    m = DeepRetentionModel(spec["arch"], spec["use_embedding"], seed, spec.get("cfg") or {})
    m.fit(ctx.tr, ctx.embs_for(ctx.tr), ctx.va, ctx.embs_for(ctx.va))
    return m


def predict_curve(m, ctx: X.Context, part: pd.DataFrame) -> np.ndarray:
    if isinstance(m, DeepRetentionModel):
        out = m.predict_videos(part, ctx.embs_for(part))
        return np.concatenate([np.clip(out[v][0], 0, 100) for v in part.video_id.unique()])
    emb = ctx.emb(part) if "emb" in m.feature_sets else None
    raw = m.predict(part, emb)
    return X.reconstruct_from_drops(part, raw) if m.target == "drop_target" else raw


def main(out=None, version=None, seed=None):
    """Trains the selected spec. `out`/`version`/`seed` let the retraining workflow build a CANDIDATE next to production.
    The splits (and therefore the protected test set) depend only on config.SEED, never on `seed`."""
    import sys
    seed = config.SEED if seed is None else int(seed)
    version = version or config.MODEL_VERSION
    spec = json.loads((config.EXPERIMENTS_DIR / "selected_model.json").read_text(encoding="utf-8"))
    key = next(k for k, v in config.EMBEDDING_MODELS.items() if v.split("/")[-1] == spec["embedding_model"])
    ctx = X.make_context(spec["segment_size"], key)
    from pathlib import Path
    out = Path(out) if out else config.MODELS_DIR / f"retention_model_{version}"
    out.mkdir(parents=True, exist_ok=True)

    primary = train_member(ctx, spec, seed)
    primary.save(out)
    members = [train_member(ctx, spec, s + seed - config.SEED) for s in ENSEMBLE_SEEDS]
    for i, m in enumerate(members):
        m.save(out / "ensemble" / f"member_{i}")

    # ---- ensemble-spread uncertainty: z calibrated on VALIDATION, coverage then checked on TEST
    def stack(part):
        return np.stack([predict_curve(m, ctx, part) for m in members])

    pv, pt = stack(ctx.va), stack(ctx.te)
    yv, yt = ctx.va["retention_target"].to_numpy(), ctx.te["retention_target"].to_numpy()
    kv, kt = ctx.va.segment_id.to_numpy() > 0, ctx.te.segment_id.to_numpy() > 0
    sv, st = pv.std(0) + 1e-6, pt.std(0) + 1e-6
    ratio = np.abs(pv.mean(0) - yv)[kv] / sv[kv]
    z = float(np.quantile(ratio, 0.90))  # z that would give 90 % coverage on validation
    cov_val = float((ratio <= z).mean())
    cov_test = float((np.abs(pt.mean(0) - yt)[kt] / st[kt] <= z).mean())
    unc_ok = 0.80 <= cov_test <= 0.97
    uncertainty = dict(available=bool(unc_ok), method=f"ensemble of {len(members)} seeds", z=z, validation_coverage=cov_val, test_coverage=cov_test,
                       rule="z set on validation for 90 % coverage; marked available only if test coverage is within 80-97 %")

    # ---- risk threshold (VALIDATION) and tau (TRAIN)
    from src.evaluation import evaluate as E

    pred_v = predict_curve(primary, ctx, ctx.va)
    risk_v = None
    if getattr(primary, "target", "") == "drop_target":
        raw = primary.predict(ctx.va, ctx.emb(ctx.va) if "emb" in primary.feature_sets else None)
        risk_v = np.maximum(raw, 0)
    elif isinstance(primary, DeepRetentionModel) and primary.cfg.get("multi_task"):
        o = primary.predict_videos(ctx.va, ctx.embs_for(ctx.va))
        risk_v = np.concatenate([np.maximum(o[v][1], 0) for v in ctx.va.video_id.unique()])
    ev = E.evaluate_split(ctx.va, pred_v, risk_v, ctx.tau, None)
    thr = M.best_threshold_f1(ev["_scores"], ev["_labels"])

    pred_t = predict_curve(primary, ctx, ctx.te)
    risk_t = None
    if risk_v is not None:
        if getattr(primary, "target", "") == "drop_target":
            raw = primary.predict(ctx.te, ctx.emb(ctx.te) if "emb" in primary.feature_sets else None)
            risk_t = np.maximum(raw, 0)
        else:
            o = primary.predict_videos(ctx.te, ctx.embs_for(ctx.te))
            risk_t = np.concatenate([np.maximum(o[v][1], 0) for v in ctx.te.video_id.unique()])
    test_eval = E.strip_private(E.evaluate_split(ctx.te, pred_t, risk_t, ctx.tau, thr))

    meta = dict(
        model_name=spec["model_name"], model_version=version, kind=spec["kind"], family=spec["family"], target=spec["target"],
        dataset_version=config.DATASET_VERSION, feature_schema_version=schema.FEATURE_SCHEMA_VERSION, trained_on=config.MODE_SYNTHETIC,
        data_mode=config.MODE_SYNTHETIC, real_validation_available=False,
        training_samples=int(ctx.tr.video_id.nunique()), validation_samples=int(ctx.va.video_id.nunique()), test_samples=int(ctx.te.video_id.nunique()),
        synthetic_samples=int(ctx.tr.video_id.nunique() + ctx.va.video_id.nunique()), real_samples=0, segment_seconds=spec["segment_size"],
        embedding_model=spec["embedding_model"], embedding_model_key=key, features=spec["features"], seed=config.SEED, model_seed=seed, ensemble_seeds=list(ENSEMBLE_SEEDS),
        training_date=datetime.now(timezone.utc).isoformat(timespec="seconds"), risk_tau=ctx.tau, risk_threshold=thr, uncertainty=uncertainty,
        test_metrics=test_eval, versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__),
        note="Trained on SYNTHETIC data; not validated on real YouTube retention.",
    )
    for lib in ("sklearn", "xgboost", "torch", "sentence_transformers", "shap"):
        try:
            meta["versions"][lib] = __import__(lib).__version__
        except Exception:  # noqa: BLE001
            pass
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=float), encoding="utf-8")
    (out / "feature_config.json").write_text(json.dumps(dict(
        feature_schema_version=schema.FEATURE_SCHEMA_VERSION, pre_publication_features=schema.PRE_PUBLICATION_FEATURES, feature_groups=schema.FEATURE_GROUPS,
        optional_groups=schema.OPTIONAL_GROUPS, post_publication_features_never_used=schema.POST_PUBLICATION_FEATURES, segment_seconds=spec["segment_size"],
        target=spec["target"], feature_sets=spec["features"]), indent=2), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("model_name", "risk_tau", "risk_threshold", "uncertainty")}, indent=2, default=float))
    print("test:", json.dumps(test_eval["regression"]))
    print("artifact:", out)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--version"); ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    main(a.out, a.version, a.seed)
