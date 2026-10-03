"""Sentence embeddings with a persistent disk cache (embeddings are never recomputed across experiments).

SentenceTransformerEmbedder: the real embedder (CPU by default, GPU automatically if available, batched).
HashingEmbedder: a deterministic lexical stand-in used ONLY for unit tests / environments without the model
download. It is not semantic and must never be used for reported results; the model metadata records which
embedder was used and inference refuses to mix them.
"""
import hashlib
import re
from pathlib import Path

import numpy as np

from src import config

_TOK = re.compile(r"[\w']+", re.U)


class Embedder:
    name: str = "base"
    dim: int = 0
    semantic: bool = True

    def encode(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, key: str = config.DEFAULT_EMBEDDING, batch_size: int = 128, device: str | None = None):
        from sentence_transformers import SentenceTransformer  # heavy import kept lazy
        import torch

        self.key = key
        self.model_id = config.EMBEDDING_MODELS.get(key, key)
        self.name = self.model_id.split("/")[-1]
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = SentenceTransformer(self.model_id, device=self.device)
        self.dim = int(self.model.get_sentence_embedding_dimension())
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        v = self.model.encode(texts, batch_size=self.batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        return v.astype(np.float32)


class HashingEmbedder(Embedder):
    name = "hashing-fallback"
    semantic = False

    def __init__(self, dim: int = 256):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in _TOK.findall((t or "").lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0 if (h >> 20) & 1 else -1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


class CachedEmbedder:
    """Wraps an Embedder; stores vectors keyed by sha1(text) in data/processed/embeddings/<name>.npz."""

    def __init__(self, base: Embedder, cache_dir: Path | None = None):
        self.base = base
        self.name, self.dim = base.name, base.dim
        self.dir = Path(cache_dir or (config.DATA_DIR / "processed" / "embeddings"))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{base.name}.npz"
        self._vecs: dict[str, np.ndarray] = {}
        if self.path.exists():
            z = np.load(self.path, allow_pickle=False)
            self._vecs = {k: v for k, v in zip(z["keys"].tolist(), z["vecs"])}
        self._dirty = False

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha1((text or "").encode("utf-8")).hexdigest()

    def encode(self, texts: list[str]) -> np.ndarray:
        keys = [self._key(t) for t in texts]
        missing = list(dict.fromkeys(t for t, k in zip(texts, keys) if k not in self._vecs))
        if missing:
            vecs = self.base.encode(missing)
            for t, v in zip(missing, vecs):
                self._vecs[self._key(t)] = v
            self._dirty = True
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._vecs[k] for k in keys])

    def save(self) -> None:
        if self._dirty:
            keys = np.array(list(self._vecs), dtype="U40")
            np.savez(self.path, keys=keys, vecs=np.stack(list(self._vecs.values())))
            self._dirty = False


class CacheOnlyEmbedder(Embedder):
    """Serves vectors ONLY from the on-disk cache (no model, no torch). Used to rebuild features from already-embedded
    text; raises if any text is missing so results can never silently depend on a different embedding."""

    def __init__(self, model_name: str, cache_dir: Path | None = None):
        path = Path(cache_dir or (config.DATA_DIR / "processed" / "embeddings")) / f"{model_name}.npz"
        z = np.load(path, allow_pickle=False)
        self._vecs = {k: v for k, v in zip(z["keys"].tolist(), z["vecs"])}
        self.name, self.dim = model_name, int(z["vecs"].shape[1])

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        keys = [CachedEmbedder._key(t) for t in texts]
        missing = [t for t, k in zip(texts, keys) if k not in self._vecs]
        if missing:
            raise KeyError(f"{len(missing)} texts are not in the embedding cache, e.g. {missing[0][:60]!r}")
        return np.stack([self._vecs[k] for k in keys])


def get_embedder(name: str = config.DEFAULT_EMBEDDING, cached: bool = True, allow_fallback: bool = False):
    """name: a key of config.EMBEDDING_MODELS, a HF model id, or 'hashing'."""
    if name == "hashing":
        base: Embedder = HashingEmbedder()
    else:
        try:
            base = SentenceTransformerEmbedder(name)
        except Exception:
            if not allow_fallback:
                raise
            base = HashingEmbedder()
    return CachedEmbedder(base) if cached else base
