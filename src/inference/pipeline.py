"""Inference pipeline: transcript + metadata -> PredictionResult.

    1 preprocess -> 2 segment -> 3 extract features -> 4 embeddings -> 5 model inference -> 6 curve construction
    -> 7 risk detection -> 8 explanation

Preprocessing, segmentation, feature extraction and the embedding model are EXACTLY the ones used in training
(`build_video_features` is shared; the artifact pins segment size, feature schema and embedding model, and loading
refuses a mismatch).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.embeddings import get_embedder
from src.evaluation.metrics import pred_risk_from_curve
from src.explainability import attribution as A
from src.features import schema
from src.features.pipeline import VideoFeatures, build_video_features
from src.inference import curve as C
from src.inference import risk as R
from src.inference.schema import ContributingFactor, NormalizedPoint, PredictionPoint, PredictionResult, RiskSegment, Uncertainty
from src.models.flat_models import FlatRetentionModel  # torch-based models are imported lazily (tree models need no torch)
from src.preprocessing import canonicalize

SYNTHETIC_WARNING = ("DEVELOPMENT / SYNTHETIC DATA: this model was trained on a synthetic gaming dataset. Its outputs demonstrate the "
                     "pipeline and must not be interpreted as real YouTube audience behaviour or as validated accuracy.")


def reconstruct_from_drops_video(drops: np.ndarray) -> np.ndarray:
    r = 100.0 - np.concatenate([[0.0], np.cumsum(drops)[:-1]])
    return np.clip(r, 0, 100)


def _load_member(d: Path):
    if (d / "model.pt").exists():
        from src.models.deep_models import DeepRetentionModel

        return DeepRetentionModel.load(d)
    return FlatRetentionModel.load(d)


def _is_deep(model) -> bool:
    return hasattr(model, "predict_videos")


class RetentionPredictor:
    def __init__(self, model_dir: Path, meta: dict, model, members: list, embedder):
        self.dir, self.meta, self.model, self.members, self.embedder = model_dir, meta, model, members, embedder
        self.segment_seconds = float(meta["segment_seconds"])
        self.tau = float(meta["risk_tau"])
        self.risk_threshold = float(meta["risk_threshold"])
        self.target = meta.get("target", "retention_target")

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, model_dir: str | Path | None = None, embedder=None) -> "RetentionPredictor":
        d = Path(model_dir or (config.MODELS_DIR / f"retention_model_{config.MODEL_VERSION}"))
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        if meta["feature_schema_version"] != schema.FEATURE_SCHEMA_VERSION:
            raise ValueError(f"model expects feature schema {meta['feature_schema_version']}, code is {schema.FEATURE_SCHEMA_VERSION}")
        emb = embedder or get_embedder(meta["embedding_model_key"])
        if emb.name != meta["embedding_model"]:
            raise ValueError(f"embedding model mismatch: trained with {meta['embedding_model']}, got {emb.name}")
        model = _load_member(d)
        members = [_load_member(p) for p in sorted((d / "ensemble").glob("member_*"))] if (d / "ensemble").exists() else []
        return cls(d, meta, model, members, emb)

    # ------------------------------------------------------------------ model inference
    def _predict_one(self, model, vf: VideoFeatures):
        if _is_deep(model):
            ret, risk = model.predict_videos(vf.table, {vf.video_id: vf.embeddings})[vf.video_id]
            return np.clip(ret, 0, 100), (np.maximum(risk, 0) if risk is not None else None)
        emb = vf.embeddings if "emb" in model.feature_sets else None
        raw = model.predict(vf.table, emb)
        if model.target == "drop_target":
            return reconstruct_from_drops_video(raw), np.maximum(raw, 0)
        return raw, None

    # ------------------------------------------------------------------ main entry
    def predict(self, video_id: str, title: str, description: str, duration: float, segments: list[dict], top_n: int = 5) -> PredictionResult:
        warnings: list[str] = []
        tr = canonicalize(video_id, segments, duration)                                  # 1 preprocess
        if tr.corrections.get("time_fixes") or tr.corrections.get("duplicates_removed"):
            warnings.append(f"transcript cleaned: {tr.corrections}")
        if not tr.cues:
            raise ValueError("transcript has no usable segments")
        vf = build_video_features(video_id, title, description, duration or tr.duration, segments, self.embedder, self.segment_seconds, transcript=tr)  # 2-4
        ret, risk = self._predict_one(self.model, vf)                                    # 5
        df = vf.table
        starts, ends = df["start_time"].to_numpy(float), df["end_time"].to_numpy(float)
        drops = risk if risk is not None else pred_risk_from_curve(ret)  # model's decline/risk head, else decline of its predicted curve

        points = [PredictionPoint(start_seconds=float(s), end_seconds=float(e), time_ratio=float(s / vf.duration), predicted_retention=float(np.clip(r, 0, 100)))
                  for s, e, r in zip(starts, ends, ret)]
        ratios, norm = C.segments_to_normalized(starts, ret, vf.duration)                # 6
        regions = R.detect_regions(starts, ends, drops, self.risk_threshold, self.tau, top_n)  # 7
        risk_segments = self._explain(vf, regions, drops)                                # 8

        if len(df) < 4:
            warnings.append("very short transcript: predictions are unreliable")
        result = PredictionResult(
            video_id=video_id, model_name=self.meta["model_name"], model_version=self.meta["model_version"],
            feature_schema_version=schema.FEATURE_SCHEMA_VERSION, dataset_version=self.meta["dataset_version"], trained_on=self.meta["trained_on"],
            data_mode_warning=SYNTHETIC_WARNING if "synthetic" in self.meta["trained_on"] else None, segment_seconds=self.segment_seconds,
            duration_seconds=float(vf.duration), embedding_model=self.meta["embedding_model"], points=points,
            normalized_curve=[NormalizedPoint(time_ratio=float(a), predicted_retention=float(b)) for a, b in zip(ratios, norm)],
            risk_segments=risk_segments, uncertainty=self._uncertainty(vf, ret), warnings=warnings,
        )
        return result

    # ------------------------------------------------------------------ explanation
    def _explain(self, vf: VideoFeatures, regions: list[dict], drops: np.ndarray) -> list[RiskSegment]:
        out: list[RiskSegment] = []
        df = vf.table
        med = df[schema.PRE_PUBLICATION_FEATURES].median()
        shap_vals = names = None
        model = self.model
        if isinstance(model, FlatRetentionModel):
            try:
                emb = vf.embeddings if "emb" in model.feature_sets else None
                shap_vals, names = A.shap_values_tree(model, df, emb)
            except Exception:  # explanation must never break the prediction
                shap_vals = None
        for reg in regions:
            idx = int(np.argmax(drops[reg["idx_start"] : reg["idx_end"] + 1])) + reg["idx_start"]
            factors: list[dict] = []
            if shap_vals is not None:
                contrib, an = A.risk_contributions(shap_vals, names, idx, model.target)
                factors = A.factors_for_segment(contrib, an, df.iloc[idx], med)
            elif _is_deep(model):
                from src.explainability import deep_attribution as DA

                eff = DA.group_ablation(model, df, {vf.video_id: vf.embeddings}, idx, use_risk_head=bool(model.cfg.get("multi_task")))
                factors = [dict(feature=g, group=g, contribution=float(v), direction="high", label=f"{g} features (ablation effect)")
                           for g, v in sorted(eff.items(), key=lambda kv: -kv[1]) if v > 0][:4]
            out.append(RiskSegment(
                start_seconds=reg["start"], end_seconds=reg["end"], risk_score=reg["risk_score"], predicted_drop=reg["total_drop"],
                contributing_features=[f["feature"] for f in factors], factors=[ContributingFactor(**f) for f in factors],
                explanation=A.explanation_text(reg["start"], reg["end"], factors),
            ))
        return out

    # ------------------------------------------------------------------ uncertainty (ensemble spread only)
    def _uncertainty(self, vf: VideoFeatures, mean_ret: np.ndarray) -> Uncertainty:
        if len(self.members) < 2:
            return Uncertainty(available=False, note="uncertainty estimate unavailable (no ensemble artifact)")
        preds = np.stack([self._predict_one(m, vf)[0] for m in self.members])
        std = preds.std(0)
        z = float(self.meta.get("uncertainty", {}).get("z", 1.645))
        cov = self.meta.get("uncertainty", {}).get("validation_coverage")
        note = ("ensemble spread (epistemic uncertainty on the model, not a guarantee); validation coverage of the interval: "
                f"{cov:.0%}" if cov is not None else "ensemble spread (epistemic); calibration not measured")
        return Uncertainty(available=True, method=f"ensemble of {len(self.members)} models", std=[float(x) for x in std],
                           lower=[float(np.clip(m - z * s, 0, 100)) for m, s in zip(mean_ret, std)],
                           upper=[float(np.clip(m + z * s, 0, 100)) for m, s in zip(mean_ret, std)], note=note)
