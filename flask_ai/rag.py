from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

import config
from telemetry import log_event

_embedder = None
_index: dict[str, Any] | None = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _chunk(text: str, source: str, max_chars: int = 800) -> list[dict[str, Any]]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    buf = ""
    section = source
    for para in paragraphs:
        heading = para.split("\n", 1)[0][:80] if para.startswith("#") else section
        if para.startswith("#"):
            section = para.lstrip("# ").strip()
        if len(buf) + len(para) > max_chars and buf:
            chunks.append({"text": buf.strip(), "source": source, "section": section})
            buf = para
        else:
            buf = f"{buf}\n\n{para}".strip()
    if buf:
        chunks.append({"text": buf.strip(), "source": source, "section": section})
    return chunks


def _load_documents() -> list[dict[str, Any]]:
    docs = []
    rag_dir = Path(config.RAG_DATA_DIR)
    if not rag_dir.exists():
        return docs
    preferred = rag_dir / "creator_policy.md"
    paths = [preferred] if preferred.exists() else [
        p for p in sorted(rag_dir.glob("*.md")) if p.name.lower() != "readme.md"
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        docs.extend(_chunk(text, path.name))
    return docs


def _tfidf_matrix(texts: list[str]) -> tuple[np.ndarray, dict[str, int]]:
    vocab: dict[str, int] = {}
    tokenized = []
    for text in texts:
        toks = _tokenize(text)
        tokenized.append(toks)
        for tok in toks:
            if tok not in vocab:
                vocab[tok] = len(vocab)
    n = len(texts)
    v = len(vocab) or 1
    tf = np.zeros((n, v), dtype=np.float32)
    df = np.zeros(v, dtype=np.float32)
    for i, toks in enumerate(tokenized):
        seen = set()
        for tok in toks:
            j = vocab[tok]
            tf[i, j] += 1.0
            if tok not in seen:
                df[j] += 1.0
                seen.add(tok)
        total = tf[i].sum() or 1.0
        tf[i] /= total
    idf = np.log((1.0 + n) / (1.0 + df)) + 1.0
    matrix = tf * idf
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms
    return matrix, vocab


def _try_fastembed(texts: list[str]):
    global _embedder
    try:
        from fastembed import TextEmbedding
    except Exception:
        return None
    if _embedder is None:
        _embedder = TextEmbedding(model_name=config.EMBEDDING_MODEL)
    vectors = list(_embedder.embed(texts))
    matrix = np.vstack([np.asarray(v, dtype=np.float32) for v in vectors])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def build_index(force: bool = False) -> dict[str, Any]:
    global _index
    store = Path(config.VECTOR_DB_DIR)
    store.mkdir(parents=True, exist_ok=True)
    meta_path = store / "index.json"
    vec_path = store / "vectors.npy"
    if not force and meta_path.exists() and vec_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        sources = {c.get("source") for c in meta.get("chunks") or []}
        if sources and sources <= {"creator_policy.md"}:
            vectors = np.load(vec_path)
            _index = {"chunks": meta["chunks"], "vectors": vectors, "backend": meta.get("backend", "tfidf"), "vocab": meta.get("vocab")}
            return _index
        force = True

    chunks = _load_documents()
    if not chunks:
        _index = {"chunks": [], "vectors": np.zeros((0, 8), dtype=np.float32), "backend": "empty", "vocab": {}}
        return _index

    texts = [c["text"] for c in chunks]
    backend = "tfidf"
    vectors = None
    vocab = {}
    if getattr(config, "EMBEDDING_BACKEND", "tfidf") == "fastembed":
        vectors = _try_fastembed(texts)
    if vectors is None:
        vectors, vocab = _tfidf_matrix(texts)
        backend = "tfidf"
    else:
        backend = "fastembed"

    np.save(vec_path, vectors)
    meta_path.write_text(json.dumps({"chunks": chunks, "backend": backend, "vocab": vocab}, ensure_ascii=False), encoding="utf-8")
    _index = {"chunks": chunks, "vectors": vectors, "backend": backend, "vocab": vocab}
    log_event("rag_indexed", chunks=len(chunks), backend=backend)
    return _index


def _embed_query(query: str, index: dict[str, Any]) -> np.ndarray:
    if index.get("backend") == "fastembed":
        vecs = _try_fastembed([query])
        if vecs is not None:
            return vecs[0]
    vocab = index.get("vocab") or {}
    vec = np.zeros(len(vocab) or 1, dtype=np.float32)
    for tok in _tokenize(query):
        if tok in vocab:
            vec[vocab[tok]] += 1.0
    n = np.linalg.norm(vec)
    if n:
        vec /= n
    return vec


def retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    index = _index or build_index()
    if not index["chunks"]:
        return []
    q = _embed_query(query, index)
    vectors = index["vectors"]
    if vectors.size == 0:
        return []
    if q.shape[0] != vectors.shape[1]:
        build_index(force=True)
        index = _index
        q = _embed_query(query, index)
        vectors = index["vectors"]
    scores = vectors @ q
    order = np.argsort(scores)[::-1][:top_k]
    results = []
    for i in order:
        if float(scores[i]) <= 0:
            continue
        chunk = dict(index["chunks"][int(i)])
        chunk["score"] = float(scores[i])
        chunk["source_id"] = f"{chunk['source']}#{chunk.get('section', '')}"
        results.append(chunk)
    return results


def facts_for_prompt(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "source_id": r["source_id"],
            "source": r["source"],
            "section": r.get("section"),
            "text": r["text"][:1200],
            "score": round(r["score"], 4),
        }
        for r in retrieve(query, top_k=top_k)
    ]
