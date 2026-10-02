# ML Integration Guide

RetainAI's data layer is finished; the ML pipeline plugs in **without touching authentication or analytics code**.
No model, prediction or fake score exists in this codebase. Anything not computed yet is `null` / `{}`.

```text
YouTube Data / Analytics / Reporting APIs
        ↓
Normalization + PostgreSQL cache
        ↓
Versioned feature contract  (this document)
        ↓
Your model (Random Forest / XGBoost / ...)
        ↓
POST /api/ml/predict  →  future_predictions table  →  dashboard "Predicted by RetainAI"
```

## 1. What the ML team receives

Two versioned contracts. Machine-readable JSON Schemas live in [`future-ml/contracts/`](../future-ml/contracts)
(regenerate with `python backend/dump_contracts.py`).

### A. Public-video feature payload (`FeaturePayload`, `schema_version: "1.0"`)

Produced by `POST /api/analyze` (public mode, API key only). Stored in `video_analysis.feature_payload`.

| Field | Source today | Notes |
| --- | --- | --- |
| `video_id`, `title`, `duration_seconds`, `category_id` | YouTube Data API | real |
| `view_count`, `like_count`, `comment_count` | YouTube Data API | real; likes/comments may be `null` if hidden |
| `language` | `defaultAudioLanguage` / `defaultLanguage` | `null` if the creator didn't set it |
| `transcript_available` | `contentDetails.caption` | boolean |
| `title_word_count`, `document_entropy`, `freshness`, `easiness`, `fraction_stopword_presence`, `speaker_speed`, `silent_period_rate` | **your preprocessing pipeline** | always `null` until you fill them (candidate features from [Video-engagement-prediction](https://github.com/Mukeshthenraj/Video-engagement-prediction)) |

`feature_readiness` in the analyze response marks each field `available` or `pending_pipeline`.

### B. Creator-video feature contract (`MLVideoFeatures`, `feature_schema_version: "1.0"`)

Produced by `GET /api/analytics/video/{video_id}/ml-features` (creator mode, OAuth session).

```json
{
  "feature_schema_version": "1.0",
  "video_id": "VIDEO_ID",
  "title": "...",
  "category": "Science & Technology",
  "duration_seconds": 542,
  "views": 100000,
  "likes": 5000,
  "comments": 300,
  "average_view_duration": 231.4,
  "average_view_percentage": 0.425,
  "retention": {
    "time_ratio": [0.01, 0.02, "..."],
    "audience_watch_ratio": [1.0, 0.97, "..."],
    "relative_retention_performance": [1.0, 0.99, "..."]
  },
  "analytics_features": { "views": 100000, "watch_time_minutes": 3200.5, "...": "..." },
  "content_features": {},
  "audio_features": {},
  "language_features": {},
  "retention_features": {}
}
```

Semantics you must preserve:

* `average_view_percentage` is a **0–1 ratio here** (YouTube returns a percent 0–100; the API divides by 100). Elsewhere in the REST API it stays a percent.
* `retention.*` are parallel arrays of **raw, unsmoothed** YouTube values over `elapsedVideoTimeRatio` (0–1 = fraction of the video). `audience_watch_ratio` is YouTube's `audienceWatchRatio` (can exceed 1 with rewatches); `relative_retention_performance` is YouTube's `relativeRetentionPerformance` (comparison with videos of similar length). They are not "retention %" and not a 0–100 score.
* `content_features`, `audio_features`, `language_features`, `retention_features` are empty objects reserved for your outputs.
* **No credentials, tokens or Google identifiers beyond the video ID are ever included.** The ML service never needs OAuth access.

## 2. Prediction contract

`POST /api/ml/predict` — **currently returns `501 ML_NOT_IMPLEMENTED`**.

Request (`PredictRequest`):

```json
{ "video_id": "abc123", "features": { "...FeaturePayload..." } }
```

Response when implemented (`PredictResponse`):

```json
{ "model_name": "random_forest", "model_version": "v1", "score": 0.78, "prediction": "high_engagement", "confidence": 0.81 }
```

Destination table (created, never written in this phase) — `future_predictions`:
`id, video_id, model_name, model_version, prediction_status, predicted_score, prediction_json, created_at`.

## 3. Exactly where to plug in

1. **Implement the interface** in [`backend/app/services/ml_service.py`](../backend/app/services/ml_service.py):

   ```python
   class RandomForestPredictionService:
       async def predict(self, request: PredictRequest) -> PredictResponse: ...
   ```

2. **Register it** in `get_prediction_service()` in the same file (currently returns `NotConnectedPredictionService`).
3. **Persist** results in `future_predictions` (model: `app/models/analysis.py::FuturePrediction`).
4. **Fill the null features** (`title_word_count`, …) in a preprocessing step before calling the model, e.g. a new `backend/app/services/feature_service.py`, or run it in `future-ml/` and write back to `video_analysis.feature_payload`.
5. **Frontend**: the dashboard's *Retention* tab already reserves a "Predicted by RetainAI" panel. When predictions exist, render the predicted curve on the same chart as the observed curve (observed data lives in `/api/analytics/video/{id}/retention`; keep the two series visually separate).

New Python dependencies (scikit-learn, xgboost, pandas, numpy, shap) go in a **separate** requirements file (e.g. `future-ml/requirements.txt`); the web backend does not need them until the service is wired in.

## 4. Training data

* Historical engagement research data: [avalanchesiqi/youtube-engagement](https://github.com/avalanchesiqi/youtube-engagement) ("Beyond Views").
* Random Forest / XGBoost / GridSearchCV / ROC-AUC baseline and feature ideas: [Mukeshthenraj/Video-engagement-prediction](https://github.com/Mukeshthenraj/Video-engagement-prediction).

Do not copy those repositories wholesale into this project; reference or adapt only what you need inside `future-ml/`.

Ground truth for *predicted vs actual retention* validation comes from creator-mode retention curves (`GET /api/analytics/video/{id}/retention`), available only for videos the signed-in creator owns.
