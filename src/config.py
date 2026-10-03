"""Central, versioned configuration for the RetainAI ML engine."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
EXPERIMENTS_DIR = ROOT / "experiments"

# --- versioning (recorded in every experiment and model artifact) -------------
DATASET_VERSION = "synthetic_v1"  # real data uses e.g. "real_v1" and lives in data/real (never mixed)
FEATURE_SCHEMA_VERSION = "1.0"
MODEL_VERSION = "v1"

SEED = 42
DEFAULT_SEGMENT_SECONDS = 15
SEGMENT_SIZES = (10, 15, 20, 30)

# data modes: kept strictly separate everywhere
MODE_SYNTHETIC = "synthetic"
MODE_REAL = "real"

# Embedding models evaluated (Experiment 8). The English model is the default for the English synthetic corpus;
# the multilingual one is required if English/Hindi/Hinglish transcripts must be supported.
EMBEDDING_MODELS = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}
DEFAULT_EMBEDDING = "minilm"


def synthetic_dir(version: str = DATASET_VERSION) -> Path:
    return DATA_DIR / "synthetic" / version


def raw_dir(version: str = DATASET_VERSION) -> Path:
    return DATA_DIR / "raw" / version


def processed_dir(version: str = DATASET_VERSION) -> Path:
    return DATA_DIR / "processed" / version
