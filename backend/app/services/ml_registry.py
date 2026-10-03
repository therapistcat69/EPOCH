"""Model registry, retraining workflow, promotion rule and the prediction-vs-actual feedback loop.

Flow:  production model -> predictions stored (prediction_history) -> creator publishes -> actual YouTube retention
       -> error + labelled example (real_training_labels) -> candidate retrained -> evaluated on the PROTECTED test split
       -> promoted ONLY if the promotion rule passes; otherwise status=rejected and production is unchanged.

Honest scope: the candidate is trained by `src.training.train_final` on the synthetic bootstrap data. Real labels are
collected and counted here, but merging them into the training table is not wired yet (real_samples stays 0 in the
artifact until it is), so the registry never claims a real-trained model.
"""
import asyncio
import hashlib
import json
import logging
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.errors import AppError
from app.models import ModelVersion, PredictionHistory, RealTrainingLabel, TrainingRun
from app.services import ml_bridge

logger = logging.getLogger("retention.ml.registry")
CANDIDATES_DIR = ml_bridge.ROOT / "models" / "candidates"
_running: dict = {"run_id": None}


def transcript_hash(segments: list[dict]) -> str:
    return hashlib.sha256(json.dumps([[s.get("start"), s.get("end"), s.get("text")] for s in segments], sort_keys=True).encode()).hexdigest()[:32]


def _row_from_meta(meta: dict, path: Path, status: str) -> ModelVersion:
    t = (meta.get("test_metrics") or {}).get("regression", {})
    return ModelVersion(
        model_name=meta["model_name"], model_version=meta["model_version"], dataset_version=meta["dataset_version"],
        feature_schema_version=meta["feature_schema_version"], training_samples=int(meta.get("training_samples") or 0),
        real_samples=int(meta.get("real_samples") or 0), synthetic_samples=int(meta.get("synthetic_samples") or 0),
        mae=t.get("mae"), rmse=t.get("rmse"), r2=t.get("r2"), pearson=t.get("pearson"), spearman=t.get("spearman"),
        status=status, artifact_path=str(path), trained_on=meta.get("trained_on", "synthetic"), metadata_json=meta,
    )


def serialize(m: ModelVersion) -> dict:
    return dict(
        id=str(m.id), model_name=m.model_name, model_version=m.model_version, dataset_version=m.dataset_version,
        feature_schema_version=m.feature_schema_version, training_samples=m.training_samples, real_samples=m.real_samples,
        synthetic_samples=m.synthetic_samples, mae=m.mae, rmse=m.rmse, r2=m.r2, pearson=m.pearson, spearman=m.spearman,
        status=m.status, trained_on=m.trained_on, created_at=m.created_at.isoformat() if m.created_at else None,
    )


async def production(session: AsyncSession) -> ModelVersion | None:
    return (await session.execute(select(ModelVersion).where(ModelVersion.status == "production"))).scalars().first()


async def ensure_production(session: AsyncSession) -> ModelVersion | None:
    """Registers the shipped artifact as production the first time (idempotent) and points inference at the registry's pick."""
    prod = await production(session)
    if prod is None:
        meta = ml_bridge.artifact_meta()
        if meta is None:
            return None
        existing = (await session.execute(select(ModelVersion).where(ModelVersion.model_version == meta["model_version"]))).scalars().first()
        prod = existing or _row_from_meta(meta, ml_bridge.DEFAULT_MODEL_DIR, "production")
        prod.status = "production"
        session.add(prod)
        await session.commit()
    if Path(prod.artifact_path) != ml_bridge.MODEL_DIR and (Path(prod.artifact_path) / "metadata.json").exists():
        ml_bridge.set_model_dir(prod.artifact_path)
    return prod


async def list_models(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(select(ModelVersion).order_by(ModelVersion.created_at.desc()))).scalars().all()
    return [serialize(r) for r in rows]


def decide(candidate: dict, prod: dict) -> tuple[bool, str]:
    """Promotion rule, evaluated on the same protected test split for both models: MAE not worse, correlation
    maintained (>= -0.01) and risk recall maintained (>= -0.05). Otherwise the candidate is rejected."""
    c, p = candidate.get("test_metrics") or {}, prod.get("test_metrics") or {}
    cr, pr, ck, pk = c.get("regression", {}), p.get("regression", {}), c.get("risk", {}), p.get("risk", {})
    checks = {
        "mae_not_worse": cr["mae"] <= pr["mae"],
        "pearson_maintained": cr["pearson"] >= pr["pearson"] - 0.01,
        "risk_recall_maintained": ck.get("risk_recall", 0) >= pk.get("risk_recall", 0) - 0.05,
    }
    ok = all(checks.values())
    msg = (f"candidate MAE {cr['mae']:.3f} vs production {pr['mae']:.3f}; Pearson {cr['pearson']:.3f} vs {pr['pearson']:.3f}; "
           f"risk recall {ck.get('risk_recall', 0):.3f} vs {pk.get('risk_recall', 0):.3f}. " + "; ".join(f"{k}={'pass' if v else 'FAIL'}" for k, v in checks.items()))
    return ok, msg


async def promote(session: AsyncSession, version: str) -> dict:
    """Promote (or roll back to) a stored version. Only one production row exists at any time."""
    target = (await session.execute(select(ModelVersion).where(ModelVersion.model_version == version))).scalars().first()
    if target is None:
        raise AppError("MODEL_NOT_FOUND", f"No model version {version}.", 404)
    if target.status == "rejected":
        raise AppError("MODEL_REJECTED", "A rejected model cannot be promoted.", 409)
    if not (Path(target.artifact_path) / "metadata.json").exists():
        raise AppError("ARTIFACT_MISSING", "The model artifact is missing on disk.", 409)
    await session.execute(update(ModelVersion).where(ModelVersion.status == "production").values(status="archived"))
    target.status = "production"
    await session.commit()
    ml_bridge.set_model_dir(target.artifact_path)
    return serialize(target)


# --------------------------------------------------------------------------- retraining
async def real_label_count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(RealTrainingLabel))).scalar_one()


async def start_retrain(factory: async_sessionmaker, reason: str, force: bool) -> dict:
    s = get_settings()
    if _running["run_id"]:
        raise AppError("RETRAIN_IN_PROGRESS", "A training run is already in progress.", 409)
    async with factory() as session:
        n_real = await real_label_count(session)
        if reason == "new_labels" and not force and n_real < s.retrain_after_real_labels:
            raise AppError("INSUFFICIENT_TRAINING_DATA", f"Only {n_real} real labelled videos; retraining after new labels needs {s.retrain_after_real_labels} (or force=true).", 409)
        prod = await production(session)
        if prod is None or ml_bridge.artifact_meta() is None:
            raise AppError("NO_PRODUCTION_MODEL", "There is no production model to retrain from.", 409)
        n_versions = (await session.execute(select(func.count()).select_from(ModelVersion))).scalar_one()
        version = f"v{n_versions + 1}"
        run = TrainingRun(model_name=prod.model_name, dataset_version=prod.dataset_version, feature_schema_version=prod.feature_schema_version,
                          reason=reason, status="running", candidate_version=version)
        session.add(run)
        await session.commit()
        run_id = run.id
    _running["run_id"] = str(run_id)
    asyncio.create_task(_train(factory, run_id, version, n_versions))
    return {"run_id": str(run_id), "candidate_version": version, "status": "running", "real_labels_available": n_real,
            "note": "Candidate is trained on the synthetic bootstrap data; real labels are not merged into training yet."}


async def _train(factory: async_sessionmaker, run_id: uuid.UUID, version: str, n_versions: int) -> None:
    out = CANDIDATES_DIR / version
    try:
        # blocking subprocess in a worker thread: asyncio subprocesses are unavailable on Windows' selector event loop
        proc = await asyncio.to_thread(
            subprocess.run, [sys.executable, "-W", "ignore", "-m", "src.training.train_final", "--out", str(out), "--version", version, "--seed", str(1000 + n_versions)],
            cwd=str(ml_bridge.ROOT), capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors="ignore")[-400:] or f"exit code {proc.returncode}")
        meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
        async with factory() as session:
            run = await session.get(TrainingRun, run_id)
            prod = await production(session)
            ok, msg = decide(meta, prod.metadata_json or ml_bridge.artifact_meta())
            cand = _row_from_meta(meta, out, "candidate")
            session.add(cand)
            run.status, run.completed_at, run.artifact_path = "completed", datetime.now(timezone.utc), str(out)
            run.training_samples, run.validation_samples, run.test_samples = (int(meta.get(k) or 0) for k in ("training_samples", "validation_samples", "test_samples"))
            run.metrics_json = meta.get("test_metrics")
            await session.commit()
            if ok:
                await promote(session, version)
                run.decision = "PROMOTED: " + msg
            else:
                cand.status = "rejected"
                run.decision = "REJECTED (production unchanged): " + msg
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - a failed training run must never affect serving
        logger.warning("training run failed: %s", type(exc).__name__)
        async with factory() as session:
            run = await session.get(TrainingRun, run_id)
            run.status, run.completed_at, run.decision = "failed", datetime.now(timezone.utc), f"training failed: {(str(exc) or type(exc).__name__)[:300]}"
            await session.commit()
    finally:
        _running["run_id"] = None


async def runs(session: AsyncSession, limit: int = 10) -> list[dict]:
    rows = (await session.execute(select(TrainingRun).order_by(TrainingRun.started_at.desc()).limit(limit))).scalars().all()
    return [dict(id=str(r.id), reason=r.reason, status=r.status, candidate_version=r.candidate_version, started_at=r.started_at.isoformat() if r.started_at else None,
                 completed_at=r.completed_at.isoformat() if r.completed_at else None, decision=r.decision) for r in rows]


# --------------------------------------------------------------------------- feedback loop
async def record_prediction(session: AsyncSession, video_row_id: uuid.UUID, segments: list[dict], prediction: dict) -> None:
    session.add(PredictionHistory(
        video_id=video_row_id, transcript_hash=transcript_hash(segments), prediction_model_version=prediction["model_version"],
        feature_schema_version=prediction["feature_schema_version"], dataset_version=prediction["dataset_version"], predicted_curve=prediction["normalized_curve"]))
    await session.commit()


def curve_error(predicted: list[dict], actual: list[dict]) -> dict:
    grid = np.linspace(0, 1, 101)
    p = np.interp(grid, [x["time_ratio"] for x in predicted], [x["predicted_retention"] for x in predicted])
    a = np.interp(grid, [x["time_ratio"] for x in actual], [x["value"] for x in actual])
    d = p - a
    corr = float(np.corrcoef(p, a)[0, 1]) if p.std() > 0 and a.std() > 0 else None
    return dict(mae=float(np.abs(d).mean()), rmse=float(np.sqrt((d ** 2).mean())), bias=float(d.mean()), pearson=corr, n_points=101)


async def record_feedback(session: AsyncSession, video_row_id: uuid.UUID, actual: list[dict]) -> dict:
    """Match the latest stored prediction to the actual YouTube retention; save the error and a labelled real example."""
    hist = (await session.execute(select(PredictionHistory).where(PredictionHistory.video_id == video_row_id).order_by(PredictionHistory.created_at.desc()))).scalars().first()
    if hist is None:
        raise AppError("NO_STORED_PREDICTION", "No prediction was stored for this video before analytics were available.", 404)
    if len(actual) < 5:
        raise AppError("ACTUAL_RETENTION_UNAVAILABLE", "Actual retention data is not available yet.", 409)
    hist.actual_curve = actual
    hist.error_metrics = curve_error(hist.predicted_curve, actual)
    label = (await session.execute(select(RealTrainingLabel).where(RealTrainingLabel.video_id == video_row_id))).scalars().first()
    if label is None:
        session.add(RealTrainingLabel(video_id=video_row_id, transcript_hash=hist.transcript_hash, actual_curve=actual))
    else:
        label.actual_curve, label.transcript_hash = actual, hist.transcript_hash
    await session.commit()
    return dict(video_id=str(video_row_id), prediction_model_version=hist.prediction_model_version, error_metrics=hist.error_metrics, labelled_example_saved=True)


async def metrics(session: AsyncSession) -> dict:
    s = get_settings()
    prod = await production(session)
    n_pred = (await session.execute(select(func.count()).select_from(PredictionHistory))).scalar_one()
    rows = (await session.execute(select(PredictionHistory).where(PredictionHistory.error_metrics.is_not(None)).order_by(PredictionHistory.created_at.desc()).limit(20))).scalars().all()
    errs = [r.error_metrics["mae"] for r in rows]
    out = dict(current_model=serialize(prod) if prod else None, prediction_count=n_pred, real_labeled_videos=await real_label_count(session),
               average_recent_error_mae=float(np.mean(errs)) if errs else None, recent_error_samples=len(errs), drift_warning=None)
    if len(errs) < s.drift_min_samples:
        out["drift_note"] = f"Not enough real labelled videos for drift monitoring ({len(errs)}/{s.drift_min_samples})."
    elif prod and prod.mae:
        out["drift_warning"] = bool(np.mean(errs) > 1.5 * prod.mae)
        out["drift_note"] = f"Recent real-data MAE {np.mean(errs):.2f} vs {prod.mae:.2f} on the synthetic protected test set (different data sources; indicative only)."
    return out
