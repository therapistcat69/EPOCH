# ML Integration (RetainAI ML engine)

The ML engine lives in the repo-root `src/` package and plugs into the existing application through **one interface**:
`backend/app/services/ml_service.py::PredictionService`. The application does not care whether the model behind it is a
Random Forest, XGBoost, LSTM or Transformer.

> **Status: a model trained on SYNTHETIC gaming data exists. It has NOT been validated on real YouTube retention.**
> `GET /api/ml/status` always says so (`trained_on`, `real_validation_available`), and the UI labels every synthetic-trained
> prediction **DEVELOPMENT / SYNTHETIC DATA**.

```text
YouTube transcript (captions / uploaded TXT·SRT·VTT / Groq Whisper)          existing transcript system
        ↓  canonical schema {video_id, segments:[{segment_id,start,end,text}]}
src/preprocessing   timestamp repair · caption cleaning · canonicalisation · configurable segmentation (10/15/20/30 s)
        ↓
src/features        linguistic · engagement · emotion · repetition · information density · topic change · hook · title alignment  (schema 1.0)
        ↓  + src/embeddings (cached sentence embeddings)
src/models          naive baselines · RF · XGBoost · MLP · BiLSTM · temporal Transformer
        ↓
src/inference       curve construction · risk regions · explanations  →  PredictionResult
        ↓
backend/app/services/ml_bridge.py + ml_service.py   (lazy, background-loaded, graceful 501/503)
        ↓
POST /api/ml/predict · GET /api/ml/status · GET /api/ml/demo/* · GET /api/video/{id}/prediction
        ↓
frontend: /video/[id] "Predicted retention" · /ml-demo       Groq explains the model's output (never alters it)
```

## Data modes (never mixed)

| Mode | Where | Used for |
| --- | --- | --- |
| **Synthetic** (`synthetic_v1`) | `data/raw`, `data/synthetic`, `data/processed` | development, debugging, architecture comparison, demos, integration tests |
| **Real** | `data/real/` | creator-authorised transcripts + actual YouTube Analytics retention (see "Real data strategy") |

Every dataset file, model artifact and `PredictionResult` carries `dataset_version` and `trained_on`/`data_mode`.

## Leakage rules

* **Pre-publication features only** are predictor inputs (`src/features/schema.py::PRE_PUBLICATION_FEATURES`): transcript, title, description, duration, segment structure, position. `POST_PUBLICATION_FEATURES` (views, likes, comments, subscribers, actual retention, average view %) are never inputs; `assert_pre_publication` raises if one appears in a model's feature list (tested).
* **Video-level, family-level splits**: segments of a video never cross splits; for synthetic data whole template families are held out. `assert_no_leakage` and the tests enforce it.
* Hyper-parameters are tuned on validation only; the test split is evaluated once per final configuration; the risk threshold τ comes from the training videos.

## Contracts

* **Feature schema** — versioned `feature_schema_version = "1.0"`; JSON Schemas in [`future-ml/contracts/`](../future-ml/contracts).
* **Request** `POST /api/ml/predict` (`app.schemas.ml.MLPredictRequest`):

  ```json
  { "video_id": "abc", "video": { "title": "...", "description": "...", "duration_seconds": 750 },
    "transcript": { "segments": [ { "segment_id": 0, "start": 0.0, "end": 12.4, "text": "..." } ] },
    "features": {} }
  ```
  `features` may carry values already computed by the application's transcript pipeline; the engine recomputes only what it needs and uses the **same** feature code as training.
* **Response** — `PredictionResult` (`src/inference/schema.py`): `points[]` (per segment: start, end, `time_ratio`, `predicted_retention`), `normalized_curve[]` (101 points on YouTube Analytics' `elapsedVideoTimeRatio` grid, so predicted vs actual can share an axis), `risk_segments[]` (start, end, `risk_score`, `predicted_drop`, `contributing_features`, `factors[]`, `explanation`, `explanation_type: "MODEL-BASED EXPLANATION"`), `uncertainty` (available only if calibrated, otherwise "uncertainty estimate unavailable"), `trained_on`, `dataset_version`, `warnings`.
* **Status** `GET /api/ml/status`: `{model_available, state, model_name, model_version, feature_schema_version, trained_on, real_validation_available, ...}`.
* **Future edit schema** (`EditSuggestion`): `{edit_type, start, end, reason, evidence, predicted_effect: null}` — `predicted_effect` stays `null` until a validated counterfactual model exists.

`risk_score` is a monotone rescaling of the predicted local decline (`clip(drop / (2τ), 0, 1)`), **not** a calibrated probability.

## Terminology the UI keeps separate

| Observed | Predicted | Model explanation | Recommendation |
| --- | --- | --- | --- |
| YouTube Analytics `audienceWatchRatio` | `PredictionResult.points` | SHAP / ablation attributions ("MODEL-BASED EXPLANATION", not causal) | Groq-written editorial experiments |

Groq receives the model's numbers and attributions and writes a plain-language explanation; it may not modify predictions, metrics, confidence or timestamps (the backend drops any explanation whose region does not match a model-supplied region).

## Where each piece lives

| Concern | Location |
| --- | --- |
| Synthetic data generation | `src/data_generation/` · [synthetic-data.md](synthetic-data.md) |
| Preprocessing / segmentation | `src/preprocessing/` |
| Features, embeddings | `src/features/`, `src/embeddings/` |
| Models, training, experiments | `src/models/`, `src/training/`, results in `experiments/` |
| Metrics, risk localisation | `src/evaluation/` |
| Explainability | `src/explainability/` |
| Inference | `src/inference/` |
| Model artifacts | `models/retention_model_v1/` (`model.pkl` \| `model.pt`, `scaler.pkl`, `feature_config.json`, `metadata.json`, `ensemble/`) |
| FastAPI integration | `backend/app/services/ml_bridge.py`, `ml_service.py`, `ml_explain_service.py`, `routes/ml.py` |
| Frontend | `frontend/src/components/ml/`, `app/ml-demo/page.tsx` |
| Model selection | [model-selection.md](model-selection.md) |

## Replacing the model / adding real data

Any new model only has to implement `predict(video_id, title, description, duration, segments) -> PredictionResult`
(see `src/inference/pipeline.py::RetentionPredictor`) or be saved in the artifact format above. To add real labels, see
the README section "Real data strategy": put creator-authorised `{video_id, transcript, actual_retention}` files in
`data/real/`, build with the same `build_dataset` code (retention resampled to the 1-second grid), train/evaluate on
**real-only** splits and report real metrics **separately** from synthetic ones.

## Reference repositories (not copied)

* [avalanchesiqi/youtube-engagement](https://github.com/avalanchesiqi/youtube-engagement) — research context on YouTube engagement.
* [Mukeshthenraj/Video-engagement-prediction](https://github.com/Mukeshthenraj/Video-engagement-prediction) — Random Forest / XGBoost / GridSearchCV baselines and candidate features (`title_word_count`, `document_entropy`, `freshness`, `easiness`, `fraction_stopword_presence`, `speaker_speed`, `silent_period_rate`); `title_word_count` is implemented, others are candidates for future feature-schema versions.

## Registry, retraining and feedback loop

See README section 12 ("Unified product, registry and continuous learning"). Endpoints: `GET /api/ml/models`, `GET /api/ml/metrics`, `POST /api/ml/predict-text`, and admin-only `POST /api/ml/retrain`, `POST /api/ml/models/{version}/promote`. Code: `backend/app/services/ml_registry.py` (promotion rule in `decide`), `src/training/train_final.py` (`--out/--version/--seed` build a candidate next to production). Verified manually: v2 candidate trained, passed the rule on the protected test split (MAE 4.730 vs 4.824), was promoted, served, and rolled back to v1.
