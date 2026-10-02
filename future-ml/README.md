# future-ml

Workspace for the ML team. Nothing here runs in production yet.

* `contracts/` — JSON Schemas generated from the backend's Pydantic models (the data you receive and the prediction you must return). Regenerate with `python backend/dump_contracts.py`.
* Full integration guide: [`../docs/ml-integration.md`](../docs/ml-integration.md).

Suggested layout when you start: `requirements.txt` (scikit-learn, xgboost, pandas, numpy, shap), `features/`, `training/`, `models/`. Read feature data from the backend API (`/api/analytics/video/{id}/ml-features`, `video_analysis.feature_payload`); you never need OAuth credentials.

References: [youtube-engagement](https://github.com/avalanchesiqi/youtube-engagement) · [Video-engagement-prediction](https://github.com/Mukeshthenraj/Video-engagement-prediction)
