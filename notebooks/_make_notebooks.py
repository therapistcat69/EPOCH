"""Generates the Colab-ready notebooks. All logic lives in `src/`; notebooks only call it and show results.

    python notebooks/_make_notebooks.py          # writes notebooks/0N_*.ipynb
    (execute for verification:  python notebooks/_run_notebooks.py)
"""
from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).resolve().parent

BOOT = '''# --- Colab / local bootstrap -------------------------------------------------------------------------
import os, sys, subprocess
IN_COLAB = "google.colab" in sys.modules
if IN_COLAB and not os.path.exists("src"):
    # Colab: upload/clone the repository first, e.g.  !git clone <your repo url> retainai && %cd retainai
    raise SystemExit("Clone or upload the repository so that the `src/` folder is in the working directory.")
if IN_COLAB:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=False)
root = os.getcwd()
while root != os.path.dirname(root) and not os.path.isdir(os.path.join(root, "src")):
    root = os.path.dirname(root)
os.chdir(root); sys.path.insert(0, root)
import torch
print("repo root:", root, "| GPU:", torch.cuda.is_available())'''

NOTEBOOKS = {
    "01_data_generation": [
        ("md", "# 01 - Synthetic data generation\n**Synthetic data is for model development and integration testing only; it must not be read as real YouTube audience behavior.**\nGenerates `synthetic_v1` (420 gaming videos, 10-15 min) with a transparent retention simulator (see `docs/synthetic-data.md`)."),
        ("code", BOOT),
        ("code", "from src.data_generation.generate import generate_dataset\nfrom src.data_generation.stats import dataset_stats\nimport json, os\nfrom src import config\nif not (config.synthetic_dir() / 'manifest.csv').exists():\n    print(generate_dataset(seed=config.SEED))\nprint(json.dumps(dataset_stats(), indent=2))"),
        ("code", "from src.data_generation import show_sample  # prints one transcript head + its retention curve\n"),
        ("code", "import matplotlib.pyplot as plt, numpy as np\nfrom src.data_generation.stats import load_retention, load_manifest\nret, man = load_retention(), load_manifest()\nfig, ax = plt.subplots(1, 2, figsize=(12, 4))\nfor a, grp in man.groupby('archetype'):\n    v = ret[grp.video_id.iloc[0]]['values']; ax[0].plot(np.linspace(0, 1, len(v)), v, label=a)\nax[0].set_title('One synthetic retention curve per archetype'); ax[0].set_xlabel('relative position'); ax[0].set_ylabel('retention %'); ax[0].legend(fontsize=6)\nax[1].hist(man.end_retention, bins=25); ax[1].set_title('Final retention (synthetic)')\nplt.show()"),
    ],
    "02_data_exploration": [
        ("md", "# 02 - Data exploration\nWhat does the synthetic corpus look like, and is it plausible? Also prints the train/validation/test **family-level** split."),
        ("code", BOOT),
        ("code", "import pandas as pd\nfrom src import config\nfrom src.data_generation.stats import dataset_stats, load_manifest\nfrom src.training.splits import family_splits, assert_no_leakage, describe_splits\nman = load_manifest()\nprint(pd.Series(dataset_stats()).to_string())\nassign = family_splits(man, config.SEED); assert_no_leakage(man, assign)\nprint(describe_splits(man, assign))"),
        ("code", "man.groupby('archetype').agg(videos=('video_id','count'), mean_duration=('duration','mean'), mean_end_retention=('end_retention','mean')).round(1)"),
    ],
    "03_preprocessing": [
        ("md", "# 03 - Preprocessing and segmentation\nTimestamp parsing/repair, caption cleaning (artifacts, duplicates; **negations are kept**), canonical transcript schema, configurable segmentation (10/15/20/30 s)."),
        ("code", BOOT),
        ("code", "from src.preprocessing import canonicalize, segment_transcript, clean_text\nfrom src.data_generation.stats import load_raw_video\nv = load_raw_video('video_0005')\nprint(clean_text('[Music]  I will   never, ever  do that ♪♪ but however … it\\'s fine !!!!'))\ntr = canonicalize(v['video_id'], v['segments'], v['duration'])\nprint(tr.corrections)\nfor seg in (10, 15, 20, 30):\n    s = segment_transcript(tr, seg, v['duration'])\n    print(seg, 's ->', len(s), 'segments; empty:', sum(x.is_empty for x in s), '| first:', s[1].start_time, s[1].end_time, round(s[1].relative_position, 3))"),
    ],
    "04_feature_engineering": [
        ("md", "# 04 - Feature engineering\nLinguistic, engagement, emotion, repetition (semantic, via embeddings), information density, topic change, hook and title-alignment features. Pre-publication features only (leakage guard)."),
        ("code", BOOT),
        ("code", "from src.embeddings import get_embedder\nfrom src.features.pipeline import build_video_features\nfrom src.features import schema\nfrom src.data_generation.stats import load_raw_video\nemb = get_embedder('minilm')\nv = load_raw_video('video_0005')\nvf = build_video_features(v['video_id'], v['title'], v['description'], v['duration'], v['segments'], emb, 15)\nprint(vf.table.shape, '| schema', schema.FEATURE_SCHEMA_VERSION)\nvf.table[['start_time','word_count','speaking_rate','semantic_novelty','redundant_information_score','topic_change_score','information_density','title_similarity']].head(8).round(2)"),
        ("code", "from src.embeddings import paraphrase_check  # cosine of paraphrases vs unrelated text\n"),
        ("code", "import json; print(json.dumps(json.load(open('experiments/emotion_eval.json'))['lexicon_emotion_accuracy_on_emotional_sentences'])) if __import__('os').path.exists('experiments/emotion_eval.json') else print('run: python -m src.evaluation.emotion_eval')"),
    ],
    "05_baseline_models": [
        ("md", "# 05 - Baselines, Random Forest, XGBoost, embeddings + XGBoost\nExperiments 1-4. Hyper-parameters are chosen on **validation** only; the test split is evaluated once per final configuration."),
        ("code", BOOT),
        ("code", "from src.training import experiments as X\nfrom src.training.run_experiments import exp1, exp2, exp3, exp4\nc = X.make_context(15, 'minilm')\nprint('train/val/test videos:', c.tr.video_id.nunique(), c.va.video_id.nunique(), c.te.video_id.nunique(), '| risk tau:', round(c.tau, 3))\nfor f in (exp1, exp3):\n    f(c)"),
    ],
    "06_sequential_models": [
        ("md", "# 06 - MLP, BiLSTM, temporal Transformer (+ multi-task)\nExperiments 5, 6, 9, 10. The Transformer is compact (dataset is small) and is **not** assumed to win."),
        ("code", BOOT),
        ("code", "from src.training import experiments as X\nfrom src.training.run_experiments import TRF_GRID, LSTM_GRID, say\nc = X.make_context(15, 'minilm')\nsay(X.run_deep(c, 'bilstm', True, LSTM_GRID[0], experiment='nb_demo', epochs=30))\nsay(X.run_deep(c, 'transformer', True, TRF_GRID[1], experiment='nb_demo', epochs=30))"),
    ],
    "07_evaluation": [
        ("md", "# 07 - Evaluation and model selection\nReads every recorded experiment (`experiments/results.jsonl`) and prints the comparison table. Cells that depend on experiments that were not run show `N/A`."),
        ("code", BOOT),
        ("code", "import os, pandas as pd\nfrom src.training.compare import build_comparison\nif os.path.exists('experiments/results.jsonl'):\n    df = build_comparison()\n    display(df)\nelse:\n    print('N/A - run: python -m src.training.run_experiments --stage all')"),
    ],
}


def build():
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
        nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in cells]
        nbf.write(nb, OUT / f"{name}.ipynb")
        print("wrote", f"{name}.ipynb")


if __name__ == "__main__":
    build()
