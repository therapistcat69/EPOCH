"""Run the 10 required experiments (+ extras). Results are appended to experiments/results.jsonl.

    python -m src.training.run_experiments --stage 1 2 3        # stages are independent and resumable
    python -m src.training.run_experiments --stage all

Protocol: every hyper-parameter grid is judged on VALIDATION only; the test split is evaluated once per final
configuration; seeds and versions are recorded with every run. Nothing here is tuned on the test set.
"""
import argparse
import sys
import time

from src import config
from src.training import experiments as X

RF_GRID = [dict(min_samples_leaf=5, max_features=0.4), dict(max_depth=16, min_samples_leaf=10, max_features=0.3), dict(min_samples_leaf=3, max_features=0.6)]
XGB_GRID = [dict(max_depth=4, learning_rate=0.05), dict(max_depth=6, learning_rate=0.05), dict(max_depth=5, learning_rate=0.03, min_child_weight=5)]
TRF_GRID = [dict(d_model=64, layers=2, heads=4, dropout=0.1), dict(d_model=128, layers=2, heads=4, dropout=0.2),
            dict(d_model=128, layers=3, heads=8, dropout=0.2), dict(d_model=256, layers=2, heads=8, dropout=0.3)]
LSTM_GRID = [dict(d_model=64, layers=1, dropout=0.1), dict(d_model=128, layers=2, dropout=0.2)]
MLP_GRID = [dict(hidden=(256, 128), dropout=0.2), dict(hidden=(128, 64), dropout=0.3)]


def say(rec):
    print(X.summarize(rec), flush=True)
    return rec


def ctx_for(seg=15, key="minilm"):
    return X.make_context(seg, key)


def exp1(c):  # naive baselines vs Random Forest
    for r in X.run_baselines(c, "exp1_naive_vs_rf"):
        say(r)
    say(X.run_flat(c, "rf", ("hand", "tfidf"), RF_GRID, experiment="exp1_naive_vs_rf"))


def exp2(c):  # Random Forest vs XGBoost (same features)
    say(X.run_flat(c, "rf", ("hand", "tfidf"), RF_GRID, experiment="exp2_rf_vs_xgb"))
    say(X.run_flat(c, "xgb", ("hand", "tfidf"), XGB_GRID, experiment="exp2_rf_vs_xgb"))


def exp3(c):  # TF-IDF vs embeddings
    say(X.run_flat(c, "xgb", ("hand", "tfidf"), XGB_GRID, experiment="exp3_tfidf_vs_emb"))
    say(X.run_flat(c, "xgb", ("hand", "emb"), XGB_GRID, experiment="exp3_tfidf_vs_emb"))


def exp4(c):  # embeddings only vs embeddings + handcrafted
    say(X.run_flat(c, "xgb", ("emb",), XGB_GRID, experiment="exp4_emb_vs_emb_hand"))
    say(X.run_flat(c, "xgb", ("hand", "emb"), XGB_GRID, experiment="exp4_emb_vs_emb_hand"))
    say(X.run_flat(c, "xgb", ("hand",), XGB_GRID, experiment="exp4_emb_vs_emb_hand"))  # handcrafted only, for reference


def exp5(c):  # independent segment models vs LSTM
    say(X.run_flat(c, "xgb", ("hand", "emb"), XGB_GRID, experiment="exp5_independent_vs_lstm"))
    say(X.run_deep_grid(c, "mlp", MLP_GRID, experiment="exp5_independent_vs_lstm"))
    say(X.run_deep_grid(c, "bilstm", LSTM_GRID, experiment="exp5_independent_vs_lstm"))


def exp6(c):  # LSTM vs Transformer
    say(X.run_deep_grid(c, "bilstm", LSTM_GRID, experiment="exp6_lstm_vs_transformer"))
    say(X.run_deep_grid(c, "transformer", TRF_GRID, experiment="exp6_lstm_vs_transformer"))


def exp7(_):  # segment sizes 10/15/20/30 s (XGB emb+hand and Transformer)
    for seg in config.SEGMENT_SIZES:
        c = ctx_for(seg)
        say(X.run_flat(c, "xgb", ("hand", "emb"), XGB_GRID, experiment="exp7_segment_size"))
        say(X.run_deep_grid(c, "transformer", [TRF_GRID[1]], experiment="exp7_segment_size"))


def exp8(_):  # embedding models: MiniLM vs multilingual MiniLM
    for key in ("minilm", "multilingual"):
        c = ctx_for(15, key)
        say(X.run_flat(c, "xgb", ("hand", "emb"), XGB_GRID, experiment="exp8_embedding_models"))
        say(X.run_deep_grid(c, "transformer", [TRF_GRID[1]], experiment="exp8_embedding_models"))


def exp9(c):  # loss functions
    base = TRF_GRID[1]
    for loss in ("mae", "mse", "huber"):
        say(X.run_deep(c, "transformer", True, dict(base, loss=loss), experiment="exp9_losses", tag=f"_loss_{loss}"))
    say(X.run_deep(c, "transformer", True, dict(base, loss="mae", curve_loss=0.5), experiment="exp9_losses", tag="_loss_mae+curve"))


def exp10(c):  # single-task vs multi-task (risk head)
    base = TRF_GRID[1]
    say(X.run_deep(c, "transformer", True, dict(base), experiment="exp10_multitask", tag="_single"))
    say(X.run_deep(c, "transformer", True, dict(base, multi_task=True, risk_weight=0.5), experiment="exp10_multitask", tag="_multitask"))
    say(X.run_deep(c, "bilstm", True, dict(LSTM_GRID[1], multi_task=True), experiment="exp10_multitask", tag="_multitask"))


def extras(c):  # target parametrisation and cumulative-context ablations (not part of the 10 required experiments)
    say(X.run_flat(c, "xgb", ("hand", "emb"), XGB_GRID, target="drop_target", experiment="extra_delta_target"))
    say(X.run_flat(c, "xgb", ("hand",), XGB_GRID, target="drop_target", experiment="extra_delta_target"))
    say(X.run_flat(c, "xgb", ("hand", "emb", "ctx"), XGB_GRID, experiment="extra_context_features"))
    say(X.run_flat(c, "rf", ("hand", "emb"), RF_GRID, experiment="extra_rf_embeddings"))


STAGES = {"1": exp1, "2": exp2, "3": exp3, "4": exp4, "5": exp5, "6": exp6, "7": exp7, "8": exp8, "9": exp9, "10": exp10, "extras": extras}
NEEDS_CTX = {"1", "2", "3", "4", "5", "6", "9", "10", "extras"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", nargs="+", default=["all"])
    a = ap.parse_args()
    stages = list(STAGES) if "all" in a.stage else a.stage
    c15 = None
    for s in stages:
        t0 = time.time()
        print(f"\n=== stage {s} ===", flush=True)
        if s in NEEDS_CTX:
            c15 = c15 or ctx_for(15)
            print(f"[train videos={c15.tr.video_id.nunique()} val={c15.va.video_id.nunique()} test={c15.te.video_id.nunique()} tau={c15.tau:.3f}]", flush=True)
            STAGES[s](c15)
        else:
            STAGES[s](None)
        print(f"--- stage {s} done in {time.time() - t0:.0f}s", flush=True)
