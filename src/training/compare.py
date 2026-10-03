"""Collate experiments/results.jsonl into the comparison tables (never fabricates: missing rows are 'N/A')."""
import json

import pandas as pd

from src import config

RESULTS = config.EXPERIMENTS_DIR / "results.jsonl"
COLS = ["experiment", "model_name", "features", "segment_size", "embedding_model", "random_seed",
        "val_mae", "test_mae", "test_rmse", "test_r2", "test_pearson", "test_spearman",
        "curve_shape_corr", "decline_shape_corr", "area_between_curves", "max_error",
        "risk_recall", "risk_precision", "top1_hit", "top3_hit", "top5_hit", "risk_iou", "chance_top3", "precision_lift",
        "ex_recall", "ex_precision", "ex_top1", "ex_top3", "ex_top5", "ex_chance_top3", "ex_lift", "ex_iou", "n_params", "inference_s_per_video"]


def load_records() -> list[dict]:
    if not RESULTS.exists():
        return []
    return [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def to_row(r: dict) -> dict:
    t, v = r["test"], r["val"]
    return dict(
        experiment=r.get("experiment", ""), model_name=r["model_name"], features=r.get("features", ""), segment_size=r["segment_size"],
        embedding_model=r.get("embedding_model", ""), random_seed=r.get("random_seed"),
        val_mae=v["regression"]["mae"], test_mae=t["regression"]["mae"], test_rmse=t["regression"]["rmse"], test_r2=t["regression"]["r2"],
        test_pearson=t["regression"]["pearson"], test_spearman=t["regression"]["spearman"],
        curve_shape_corr=t["curve"]["curve_shape_corr"], decline_shape_corr=t["curve"]["decline_shape_corr"],
        area_between_curves=t["curve"]["area_between_curves"], max_error=t["curve"]["max_error"],
        risk_recall=t["risk"]["risk_recall"], risk_precision=t["risk"]["risk_precision"], top1_hit=t["risk"]["top1_hit"],
        top3_hit=t["risk"]["top3_hit"], top5_hit=t["risk"]["top5_hit"], risk_iou=t["risk"]["risk_iou"],
        chance_top3=t["risk"]["chance_top3"], precision_lift=t["risk"]["precision_lift"],
        ex_recall=t["risk_excess"]["risk_recall"], ex_precision=t["risk_excess"]["risk_precision"], ex_top1=t["risk_excess"]["top1_hit"],
        ex_top3=t["risk_excess"]["top3_hit"], ex_top5=t["risk_excess"]["top5_hit"], ex_chance_top3=t["risk_excess"]["chance_top3"],
        ex_lift=t["risk_excess"]["precision_lift"], ex_iou=t["risk_excess"]["risk_iou"],
        n_params=r.get("n_params"), inference_s_per_video=r.get("inference_seconds_per_video"),
    )


def build_comparison(write: bool = True) -> pd.DataFrame:
    recs = load_records()
    if not recs:
        return pd.DataFrame(columns=COLS)
    latest: dict[tuple, dict] = {}
    for r in recs:  # later records of the same configuration replace earlier ones
        latest[(r.get("experiment", ""), r["model_name"], r.get("features", ""), r["segment_size"], r.get("embedding_model", ""), r.get("random_seed"))] = r
    df = pd.DataFrame([to_row(r) for r in latest.values()])[COLS].sort_values(["experiment", "val_mae"]).reset_index(drop=True)
    if write:
        config.EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(config.EXPERIMENTS_DIR / "final_comparison.csv", index=False)
    return df


FAMILIES = [
    ("Naive (mean by position)", lambda r: r["model_name"] == "naive_mean_by_position"),
    ("Random Forest", lambda r: r["model_name"] == "rf" and r["features"] == "hand+tfidf"),
    ("XGBoost (TF-IDF)", lambda r: r["model_name"] == "xgb" and r["features"] == "hand+tfidf"),
    ("Embedding + XGBoost", lambda r: r["model_name"] == "xgb" and r["features"] == "hand+emb"),
    ("MLP", lambda r: r["model_name"].startswith("mlp") and "_mt" not in r["model_name"]),
    ("BiLSTM", lambda r: r["model_name"].startswith("bilstm") and "_mt" not in r["model_name"]),
    ("Transformer", lambda r: r["model_name"].startswith("transformer") and "_mt" not in r["model_name"] and "loss" not in r["model_name"]),
]


def research_table(seg: int = config.DEFAULT_SEGMENT_SECONDS, embedding: str = "all-MiniLM-L6-v2") -> pd.DataFrame:
    """Spec table: Model | Features | MAE | RMSE | R2 | Correlation | Risk Recall - actual measured values or 'N/A'."""
    recs = [r for r in load_records() if r["segment_size"] == seg and r.get("embedding_model") in (embedding, None, "")
            or (r["segment_size"] == seg and r["features"] == "relative_position")]
    rows = []
    for label, pred in FAMILIES:
        cands = [r for r in recs if pred(r)]
        if not cands:
            rows.append(dict(Model=label, Features="N/A", MAE="N/A", RMSE="N/A", R2="N/A", Correlation="N/A",
                             **{"Risk Recall": "N/A", "Excess-risk Top-3 (chance 0.27)": "N/A", "Excess-risk Lift": "N/A"}))
            continue
        best = min(cands, key=lambda r: r["val"]["regression"]["mae"])  # choose by VALIDATION
        t = best["test"]
        rows.append(dict(Model=label, Features=best["features"], MAE=round(t["regression"]["mae"], 2), RMSE=round(t["regression"]["rmse"], 2),
                         R2=round(t["regression"]["r2"], 3), Correlation=round(t["regression"]["pearson"], 3),
                         **{"Risk Recall": round(t["risk"]["risk_recall"], 3), "Excess-risk Top-3 (chance 0.27)": round(t["risk_excess"]["top3_hit"], 2),
                            "Excess-risk Lift": round(t["risk_excess"]["precision_lift"], 2)}))
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    pd.set_option("display.width", 250, "display.max_columns", 40)
    df = build_comparison()
    print(df.round(3).to_string())
    print()
    print(markdown_table(research_table()))
