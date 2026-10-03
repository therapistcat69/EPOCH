"""Per-segment (independent) models: Random Forest and XGBoost on handcrafted / TF-IDF / embedding features.

Feature sets (combinable):
    'hand'  handcrafted PRE-publication features (+ relative position and video-level hook/title numbers)
    'tfidf' TF-IDF of the cleaned segment text (vectoriser fit on TRAIN text only)
    'emb'   dense sentence-embedding of the segment
    'ctx'   optional cumulative-history columns (schema.OPTIONAL_GROUPS['context'])
The leakage guard `assert_pre_publication` runs on every feature list.
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer

from src import config
from src.features import schema


def stack_embeddings(df: pd.DataFrame, embs: dict[str, np.ndarray]) -> np.ndarray:
    out = np.zeros((len(df), next(iter(embs.values())).shape[1]), dtype=np.float32)
    pos = 0
    for vid, g in df.groupby("video_id", sort=False):
        e = embs[vid]
        out[pos : pos + len(g)] = e[g.segment_id.to_numpy()]
        pos += len(g)
    return out


class FlatRetentionModel:
    def __init__(self, kind: str = "xgb", feature_sets: tuple = ("hand",), seed: int = config.SEED, params: dict | None = None,
                 target: str = "retention_target"):
        assert kind in ("rf", "xgb")
        self.kind, self.feature_sets, self.seed, self.params, self.target = kind, tuple(feature_sets), seed, dict(params or {}), target
        self.name = f"{kind}_{'+'.join(self.feature_sets)}"
        self.hand_cols = list(schema.PRE_PUBLICATION_FEATURES) + (list(schema.CONTEXT_COLUMNS) if "ctx" in self.feature_sets else [])
        schema.assert_pre_publication(self.hand_cols)
        self.tfidf = None
        self.model = None

    # ---- features
    def _matrix(self, df: pd.DataFrame, emb: np.ndarray | None, fit: bool = False):
        """Dense float32 matrix unless TF-IDF is used (then sparse). Dense matters for XGBoost: absent entries of a
        scipy-sparse matrix are treated as MISSING (not zero), which silently changes tree routing and breaks SHAP additivity."""
        parts = []
        dense = df[self.hand_cols].to_numpy(dtype=np.float32)
        if "hand" in self.feature_sets or "ctx" in self.feature_sets:
            parts.append(dense)
        else:  # position is always allowed (retention naturally depends on where the segment is)
            keep = [self.hand_cols.index(c) for c in ("relative_position", "absolute_time", "duration_seconds")]
            parts.append(dense[:, keep])
        if "tfidf" in self.feature_sets:
            if fit:
                self.tfidf = TfidfVectorizer(max_features=500, ngram_range=(1, 2), min_df=3, sublinear_tf=True)
                self.tfidf.fit(df["text"].fillna(""))
            parts.append(self.tfidf.transform(df["text"].fillna("")))
        if "emb" in self.feature_sets:
            if emb is None:
                raise ValueError("embedding feature set requires embeddings")
            parts.append(emb.astype(np.float32))
        if any(sparse.issparse(p) for p in parts):
            return sparse.hstack([sparse.csr_matrix(p) if not sparse.issparse(p) else p for p in parts], format="csr")
        return np.hstack(parts)

    def feature_names(self) -> list[str]:
        names = list(self.hand_cols) if ("hand" in self.feature_sets or "ctx" in self.feature_sets) else ["relative_position", "absolute_time", "duration_seconds"]
        if "tfidf" in self.feature_sets:
            names += [f"tfidf_{t}" for t in self.tfidf.get_feature_names_out()]
        if "emb" in self.feature_sets:
            names += [f"emb_{i}" for i in range(self.emb_dim)]
        return names

    # ---- fit / predict
    def fit(self, df: pd.DataFrame, emb: np.ndarray | None, df_val: pd.DataFrame | None = None, emb_val: np.ndarray | None = None):
        self.emb_dim = emb.shape[1] if emb is not None else 0
        X = self._matrix(df, emb, fit=True)
        y = df[self.target].to_numpy(dtype=float)
        if self.kind == "rf":
            p = dict(n_estimators=300, max_depth=None, min_samples_leaf=5, max_features=0.4, n_jobs=-1, random_state=self.seed)
            p.update(self.params)
            self.model = RandomForestRegressor(**p).fit(X, y)
        else:
            from xgboost import XGBRegressor

            p = dict(n_estimators=800, learning_rate=0.05, max_depth=5, subsample=0.8, colsample_bytree=0.6, min_child_weight=3,
                     reg_lambda=2.0, tree_method="hist", n_jobs=-1, random_state=self.seed, early_stopping_rounds=40)
            p.update(self.params)
            self.model = XGBRegressor(**p)
            if df_val is not None:
                self.model.fit(X, y, eval_set=[(self._matrix(df_val, emb_val), df_val[self.target].to_numpy(float))], verbose=False)
            else:
                self.model.set_params(early_stopping_rounds=None)
                self.model.fit(X, y)
        return self

    def predict(self, df: pd.DataFrame, emb: np.ndarray | None = None) -> np.ndarray:
        pred = self.model.predict(self._matrix(df, emb))
        return np.clip(pred, 0, 100) if self.target == "retention_target" else pred

    # ---- persistence (model + preprocessing together)
    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        joblib.dump(dict(kind=self.kind, feature_sets=self.feature_sets, seed=self.seed, params=self.params, target=self.target, hand_cols=self.hand_cols,
                         tfidf=self.tfidf, model=self.model, emb_dim=self.emb_dim), path / "model.pkl")

    @classmethod
    def load(cls, path: Path) -> "FlatRetentionModel":
        d = joblib.load(path / "model.pkl")
        m = cls(d["kind"], d["feature_sets"], d["seed"], d["params"], d["target"])
        m.hand_cols, m.tfidf, m.model, m.emb_dim = d["hand_cols"], d["tfidf"], d["model"], d["emb_dim"]
        return m
