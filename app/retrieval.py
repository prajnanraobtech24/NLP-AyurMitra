
"""Hybrid evidence retrieval with cached lexical indexes and opt-in dense embeddings."""
from __future__ import annotations

import math
import re
import hashlib
import os
import unicodedata
from difflib import SequenceMatcher
from collections import Counter, OrderedDict, defaultdict
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer


TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)
_HYBRID_INDEXES = OrderedDict()


def tokens(text: str) -> list[str]:
    out = []
    for raw in TOKEN_RE.findall(str(text or "")):
        folded = unicodedata.normalize("NFKD", raw.lower())
        has_diacritic = any(unicodedata.combining(char) for char in folded)
        token = "".join(char for char in folded if not unicodedata.combining(char))
        if len(token) > 1:
            out.append(token)
            # Common Latin transliterations spell Sanskrit visarga as ḥ/H; ordinary
            # English queries omit it (for example, āyurvedaḥ -> ayurveda).
            if has_diacritic and token.endswith("h") and len(token) > 3:
                out.append(token[:-1])
    return out


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


def _get_hybrid_index(records: list[dict[str, Any]], text_key: str) -> dict:
    """Build lexical statistics once per stable evidence list."""
    key = (id(records), text_key)
    cached = _HYBRID_INDEXES.get(key)
    if cached is not None and cached["records"] is records:
        _HYBRID_INDEXES.move_to_end(key)
        return cached

    texts = [str(record.get(text_key, "")) for record in records]
    postings = defaultdict(list)
    plant_lookup = defaultdict(set)
    lengths = []
    for doc_id, text in enumerate(texts):
        frequencies = Counter(tokens(text))
        lengths.append(sum(frequencies.values()))
        for term, frequency in frequencies.items():
            postings[term].append((doc_id, frequency))
        record = records[doc_id]
        if record.get("plant"):
            plant_lookup[_normalize_name(record["plant"])].add(doc_id)
            aliases = record.get("plant_aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            for alias in aliases:
                if alias:
                    plant_lookup[_normalize_name(alias)].add(doc_id)

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), max_features=50000, strip_accents="unicode"
    )
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        matrix = None
        vectorizer = None

    vocabulary_by_length: dict[int, list[str]] = defaultdict(list)
    for word in postings:
        vocabulary_by_length[len(word)].append(word)

    result = {
        "records": records,
        "texts": texts,
        "postings": postings,
        "vocabulary_by_length": vocabulary_by_length,
        "plant_lookup": plant_lookup,
        "lengths": lengths,
        "avgdl": sum(lengths) / max(len(lengths), 1),
        "vectorizer": vectorizer,
        "matrix": matrix,
    }
    _HYBRID_INDEXES[key] = result
    while len(_HYBRID_INDEXES) > 3:
        _HYBRID_INDEXES.popitem(last=False)
    return result


def correct_query_spelling(query: str, records: list[dict[str, Any]], text_key: str = "text") -> str:
    """Correct only high-confidence one/two-character typos against this corpus."""
    if not query or not records:
        return query
    index = _get_hybrid_index(records, text_key)
    vocabulary = index["postings"]
    corrected = query
    known_variants = {
        "ayurvedaa": "ayurveda",
        "ashwaganda": "ashwagandha",
        "ashwagandh": "ashwagandha",
        "tumeric": "turmeric",
        "curcumae": "curcuma",
    }
    for misspelling, canonical in known_variants.items():
        corrected = re.sub(rf"(?i)(?<!\w){misspelling}(?!\w)", canonical, corrected)
    for token in dict.fromkeys(re.findall(r"[A-Za-z][A-Za-z'-]{5,}", query)):
        folded = token.lower()
        if folded in vocabulary:
            continue
        candidates = [
            word
            for length in range(max(1, len(folded) - 2), len(folded) + 3)
            for word in index["vocabulary_by_length"].get(length, ())
        ]
        ranked = sorted(
            ((SequenceMatcher(None, folded, word).ratio(), word) for word in candidates),
            reverse=True,
        )
        if not ranked or ranked[0][0] < 0.88:
            continue
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.04:
            continue
        corrected = re.sub(rf"(?i)(?<!\w){re.escape(token)}(?!\w)", ranked[0][1], corrected, count=1)
    return corrected


def _indexed_bm25(query: str, index: dict) -> list[float]:
    terms = tokens(query)
    count = len(index["lengths"])
    scores = [0.0] * count
    if not terms or not count:
        return scores
    avgdl = index["avgdl"] or 1.0
    for term in terms:
        matches = index["postings"].get(term, ())
        df = len(matches)
        if not df:
            continue
        idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
        for doc_id, frequency in matches:
            length = index["lengths"][doc_id]
            denom = frequency + 1.5 * (1 - 0.75 + 0.75 * length / avgdl)
            scores[doc_id] += idf * frequency * 2.5 / denom
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

    index = _get_hybrid_index(records, text_key)

    # Remove common question words so the subject terms receive more weight.
    stop = {
        "what", "is", "are", "the", "a", "an", "in", "of", "for",
        "to", "and", "does", "do", "mean", "tell", "me", "about",
        "how", "can", "i", "please", "explain",
    }

    q_terms = [t for t in tokens(query) if t not in stop]
    retrieval_query = " ".join(q_terms) or query

    bm = _indexed_bm25(retrieval_query, index)

    # The corpus matrix is cached; only the small query vector is built per search.
    try:
        if index["matrix"] is None:
            raise ValueError("empty retrieval vocabulary")
        query_vector = index["vectorizer"].transform([retrieval_query])
        sparse = (index["matrix"] @ query_vector.T).toarray().ravel().tolist()
    except ValueError:
        sparse = [0.0] * len(records)

    dense_enabled = os.environ.get("AYURMITRA_ENABLE_DENSE", "").lower() in {"1", "true", "yes", "on"}
    dense = _dense_scores(retrieval_query, index["texts"]) if dense_enabled else None

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
    if index["plant_lookup"]:
        exact_ids = index["plant_lookup"].get(_normalize_name(query), set())
        exact_matches = [i in exact_ids for i in range(len(records))]
    else:
        exact_matches = [False] * len(records)

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
