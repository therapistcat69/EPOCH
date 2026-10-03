"""Evidence-based primary-model selection. Uses VALIDATION metrics only; test numbers are reported afterwards.

Documented rule (applied mechanically, so the written justification always matches the measured numbers):
  1. Candidates = trained models at the default segment size / embedding (excludes naive baselines).
  2. 'Statistically similar set' = candidates whose validation MAE is within max(0.5 pts, 5 %) of the best validation MAE.
  3. Within that set prefer, in order: higher validation top-3 risk hit, lower inference cost, simpler/more interpretable
     family (tree < MLP < BiLSTM < Transformer).
  If a deep model beats every other family by more than the tolerance it is selected outright - the goal is the best
  scientifically justified prototype, not the most complicated one.

Outputs: experiments/selected_model.json, experiments/final_comparison.csv, docs/model-selection.md
"""
import json

from src import config
from src.training import compare

FAMILY_RANK = {"rf": 0, "xgb": 0, "mlp": 1, "bilstm": 2, "transformer": 3}
DEEP = ("mlp", "bilstm", "transformer")


def family(r: dict) -> str:
    n = r["model_name"]
    for k in ("transformer", "bilstm", "mlp", "xgb", "rf"):
        if n.startswith(k):
            return k
    return n


def eligible(r: dict, seg: int, emb: str) -> bool:
    if r["segment_size"] != seg or r["model_name"].startswith("naive"):
        return False
    if r.get("embedding_model") not in (emb, None, ""):
        return False
    return r.get("experiment", "") not in ("exp7_segment_size", "exp8_embedding_models") or (r["segment_size"] == seg and r.get("embedding_model") == emb)


def select(seg: int = config.DEFAULT_SEGMENT_SECONDS, emb: str = "all-MiniLM-L6-v2") -> dict:
    recs = [r for r in compare.load_records() if eligible(r, seg, emb)]
    if not recs:
        raise SystemExit("no experiment results found - run src.training.run_experiments first")
    # latest record per configuration
    latest = {}
    for r in recs:
        latest[(r["model_name"], r["features"], json.dumps(r.get("config") or r.get("best_params") or {}, sort_keys=True, default=str), r.get("experiment"))] = r
    cands = list(latest.values())
    best_mae = min(r["val"]["regression"]["mae"] for r in cands)
    tol = max(0.5, 0.05 * best_mae)
    similar = [r for r in cands if r["val"]["regression"]["mae"] <= best_mae + tol]

    def cost(r):
        return r.get("inference_seconds_per_video") or 0.0

    # risk localisation = position-ADJUSTED top-3 hit on validation (absolute top-k is dominated by the early-video decline)
    similar.sort(key=lambda r: (-round(r["val"]["risk_excess"]["top3_hit"], 2), FAMILY_RANK[family(r)], cost(r), r["val"]["regression"]["mae"]))
    chosen = similar[0]
    return dict(chosen=chosen, similar=similar, all=cands, best_val_mae=best_mae, tolerance=tol)


def describe(r: dict) -> str:
    t, v = r["test"], r["val"]
    return (f"{r['model_name']} ({r['features']}): val MAE {v['regression']['mae']:.2f}, test MAE {t['regression']['mae']:.2f}, "
            f"test R² {t['regression']['r2']:.3f}, test Pearson {t['regression']['pearson']:.3f}, excess-risk top-3 {t['risk_excess']['top3_hit']:.2f} "
            f"(chance {t['risk_excess']['chance_top3']:.2f}), excess lift {t['risk_excess']['precision_lift']:.2f}")


def write_outputs(sel: dict) -> dict:
    chosen = sel["chosen"]
    fam = family(chosen)
    spec = dict(
        kind="deep" if fam in DEEP else "flat", family=fam, model_name=chosen["model_name"], features=chosen["features"],
        segment_size=chosen["segment_size"], embedding_model=chosen["embedding_model"],
        target="drop_target" if "_delta" in chosen["model_name"] else "retention_target",
        params=chosen.get("best_params"), arch=fam if fam in DEEP else None, cfg=chosen.get("config"), use_embedding="emb" in chosen["features"],
        selection_rule="validation MAE within tolerance, then risk top-3, then cost, then interpretability (see docs/model-selection.md)",
        val_mae=chosen["val"]["regression"]["mae"],
    )
    (config.EXPERIMENTS_DIR / "selected_model.json").write_text(json.dumps(spec, indent=2, default=str), encoding="utf-8")
    compare.build_comparison()

    deep_best = min((r for r in sel["all"] if family(r) in ("bilstm", "transformer")), key=lambda r: r["val"]["regression"]["mae"], default=None)
    tree_best = min((r for r in sel["all"] if family(r) in ("rf", "xgb")), key=lambda r: r["val"]["regression"]["mae"], default=None)
    lines = ["# Model selection", "",
             "> All numbers below are measured on the **synthetic development dataset** (`synthetic_v1`). They compare models on a generated world and are not evidence of real-world YouTube retention accuracy.", "",
             f"**Selected primary model:** `{chosen['model_name']}` with features `{chosen['features']}` (segment size {chosen['segment_size']} s, embeddings `{chosen['embedding_model']}`).", "",
             "## Rule (validation data only)", "",
             "1. Candidates: trained models at the default segmentation/embedding (naive baselines excluded).",
             f"2. Similar-performance set: validation MAE within max(0.5 pts, 5 %) = **{sel['tolerance']:.2f}** of the best ({sel['best_val_mae']:.2f}).",
             "3. Within that set: higher validation **position-adjusted** top-3 risk hit (absolute top-k is dominated by the steep early-video decline, which position alone already finds), then lower inference cost, then simpler/more interpretable family (tree < MLP < BiLSTM < Transformer).",
             "4. A deep model that beats the other families by more than the tolerance is selected outright.", "",
             "## Why this model", ""]
    if tree_best and deep_best:
        d = deep_best["val"]["regression"]["mae"] - tree_best["val"]["regression"]["mae"]
        if fam in ("rf", "xgb", "mlp"):
            lines.append(f"The best tree model ({tree_best['model_name']}, val MAE {tree_best['val']['regression']['mae']:.2f}) and the best sequence model ({deep_best['model_name']}, val MAE {deep_best['val']['regression']['mae']:.2f}) "
                         f"differ by {d:+.2f} MAE points (tolerance {sel['tolerance']:.2f}). "
                         + ("The sequence models did **not** improve meaningfully over the simpler model, so the simpler/cheaper model was kept." if d > -sel["tolerance"] else "The simpler model was preferred on risk localisation/cost within the tolerance."))
        else:
            lines.append(f"The sequence model {chosen['model_name']} improved validation MAE by {-d:.2f} points over the best tree model, which exceeds the tolerance ({sel['tolerance']:.2f}), so the deep model was selected.")
    lines += ["", "## Candidates (validation | test)", "", "| Model | Features | Val MAE | Test MAE | Test RMSE | Test R² | Pearson | Curve-shape corr | Excess-risk top-3 (chance) | Excess-risk lift | Params | s / video |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(sel["all"], key=lambda r: r["val"]["regression"]["mae"])[:25]:
        t = r["test"]
        mark = " **(selected)**" if r is chosen else ""
        lines.append(f"| {r['model_name']}{mark} | {r['features']} | {r['val']['regression']['mae']:.2f} | {t['regression']['mae']:.2f} | {t['regression']['rmse']:.2f} | {t['regression']['r2']:.3f} | "
                     f"{t['regression']['pearson']:.3f} | {t['curve']['curve_shape_corr']:.3f} | {t['risk_excess']['top3_hit']:.2f} ({t['risk_excess']['chance_top3']:.2f}) | {t['risk_excess']['precision_lift']:.2f} | {r.get('n_params') or '-'} | {(r.get('inference_seconds_per_video') or 0):.3f} |")
    lines += ["", "## Caveat", "",
              "Because the data are synthetic, differences between models may reflect how easily each family inverts the generator rather than real predictive ability. "
              "Selection must be repeated on real creator-authorised retention data before any real-world claim (see README, 'Real data strategy')."]
    (config.ROOT / "docs").mkdir(exist_ok=True)
    (config.ROOT / "docs" / "model-selection.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return spec


if __name__ == "__main__":
    s = select()
    print("selected:", describe(s["chosen"]))
    print("similar set:", [r["model_name"] + ":" + r["features"] for r in s["similar"]])
    print(json.dumps(write_outputs(s), indent=2, default=str))
