
"""Hybrid evidence retrieval: BM25 lexical + TF-IDF fallback + optional multilingual dense embeddings.

Dense embeddings are optional so the app remains runnable on a student laptop without model downloads.
When sentence-transformers and faiss-cpu are installed, semantic retrieval is enabled automatically.
"""
from __future__ import annotations

import math
import re
import hashlib
from collections import Counter
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [
        t.lower()
        for t in TOKEN_RE.findall(str(text or ""))
        if len(t) > 1
    ]


def bm25_scores(
    query: str,
    documents: list[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Small, dependency-free BM25 implementation for local corpora."""
    if not documents:
        return []

    q = tokens(query)
    docs = [tokens(d) for d in documents]

    if not q:
        return [0.0] * len(docs)

    n = len(docs)
    avgdl = sum(map(len, docs)) / max(n, 1)
    df = Counter(term for doc in docs for term in set(doc))
    scores = []

    for doc in docs:
        tf = Counter(doc)
        score = 0.0
        dl = len(doc)

        for term in q:
            if term not in tf:
                continue

            idf = math.log(
                1 + (n - df[term] + 0.5) / (df[term] + 0.5)
            )
            denom = tf[term] + k1 * (
                1 - b + b * dl / max(avgdl, 1)
            )
            score += idf * tf[term] * (k1 + 1) / denom

        scores.append(score)

    return scores


def _dense_scores(
    query: str,
    documents: list[str],
) -> list[float] | None:
    """Return semantic similarity scores when optional dependencies are available."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        import os

        model_name = os.environ.get(
            "AYURMITRA_EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )

        global _MODEL, _DENSE_CACHE

        try:
            model = _MODEL
        except NameError:
            _MODEL = SentenceTransformer(model_name)
            model = _MODEL

        if "_DENSE_CACHE" not in globals():
            _DENSE_CACHE = {}

        key = hashlib.sha256(
            (model_name + "\n" + "\n".join(documents)).encode(
                "utf-8", errors="ignore"
            )
        ).hexdigest()

        cached = _DENSE_CACHE.get(key)

        if cached is None:
            vectors = model.encode(
                documents,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vectors = np.asarray(vectors, dtype="float32")

            index = None
            try:
                import faiss

                index = faiss.IndexFlatIP(vectors.shape[1])
                index.add(vectors)
            except Exception:
                index = None

            cached = (vectors, index)
            _DENSE_CACHE[key] = cached

        vectors, index = cached

        qv = np.asarray(
            model.encode(
                [query],
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype="float32",
        )

        if index is not None:
            scores, ids = index.search(qv, len(documents))
            result = [0.0] * len(documents)

            for score, idx in zip(scores[0], ids[0]):
                if idx >= 0:
                    result[int(idx)] = float(score)

            return result

        return (vectors @ qv[0]).astype(float).tolist()

    except Exception:
        return None


def _normalize_name(value: Any) -> str:
    """Normalize a plant name or alias for exact-name comparison."""
    value = str(value or "").lower().strip()
    value = re.sub(r"[^\w\s-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _exact_plant_match(
    query: str,
    record: dict[str, Any],
) -> bool:
    """Check whether the whole query matches a plant name or one of its aliases."""
    normalized_query = _normalize_name(query)

    if not normalized_query:
        return False

    plant_name = _normalize_name(record.get("plant", ""))

    aliases = record.get("plant_aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]

    normalized_aliases = {
        _normalize_name(alias)
        for alias in aliases
        if alias
    }

    return (
        normalized_query == plant_name
        or normalized_query in normalized_aliases
    )


def hybrid_search(
    query: str,
    records: list[dict[str, Any]],
    text_key: str = "text",
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Retrieve relevant records, prioritizing exact plant-name matches."""
    if not query or not query.strip() or not records or top_k <= 0:
        return []

    texts = [str(r.get(text_key, "")) for r in records]

    # Remove common question words so the subject terms receive more weight.
    stop = {
        "what", "is", "are", "the", "a", "an", "in", "of", "for",
        "to", "and", "does", "do", "mean", "tell", "me", "about",
        "how", "can", "i", "please", "explain",
    }

    q_terms = [t for t in tokens(query) if t not in stop]
    retrieval_query = " ".join(q_terms) or query

    bm = bm25_scores(retrieval_query, texts)

    # Sparse TF-IDF provides a lightweight complementary ranking signal.
    try:
        vec = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=50000,
            strip_accents="unicode",
        )
        matrix = vec.fit_transform(texts + [retrieval_query])
        sparse = cosine_similarity(
            matrix[-1], matrix[:-1]
        ).ravel().tolist()
    except ValueError:
        sparse = [0.0] * len(records)

    dense = _dense_scores(retrieval_query, texts)

    def norm(scores: list[float]) -> list[float]:
        maximum = max(scores, default=0.0)
        return [
            score / maximum if maximum > 0 else 0.0
            for score in scores
        ]

    bn = norm(bm)
    sn = norm(sparse)

    if dense is not None:
        dn = [
            max(0.0, min(1.0, (score + 1) / 2))
            for score in dense
        ]
        combined = [
            0.40 * a + 0.20 * b + 0.40 * c
            for a, b, c in zip(bn, sn, dn)
        ]
        method = "BM25 + TF-IDF + multilingual dense embeddings"
    else:
        combined = [
            0.65 * a + 0.35 * b
            for a, b in zip(bn, sn)
        ]
        method = "BM25 + TF-IDF (dense model not installed)"

    # Exact plant-name or common-name matches rank ahead of partial matches.
    # Example: "turmeric" should prioritize Curcuma longa, whose aliases
    # include "Turmeric", over Curcuma aromatica ("Wild Turmeric").
    exact_matches = [
        _exact_plant_match(query, record)
        for record in records
    ]

    ids = sorted(
        range(len(records)),
        key=lambda i: (exact_matches[i], combined[i]),
        reverse=True,
    )

    out = []

    for i in ids:
        # Keep the original behavior of excluding records with no retrieval score.
        if combined[i] <= 0:
            continue

        item = dict(records[i])
        item["retrieval_score"] = round(float(combined[i]), 4)
        item["retrieval_method"] = method
        out.append(item)

        if len(out) >= top_k:
            break

    return out
