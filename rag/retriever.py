"""
retriever.py
------------
Phase 6: given a query (typically an error message), retrieve the most
relevant chunks from the docs/ corpus using TF-IDF + cosine similarity.

Usage:
    from retriever import retrieve
    chunks = retrieve("KeyError: 'regionn'", top_k=2)
"""

import os
import pickle
from sklearn.metrics.pairwise import cosine_similarity

INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.pkl")

_index_cache = None  # loaded once, reused across calls


def _load_index():
    global _index_cache
    if _index_cache is None:
        if not os.path.exists(INDEX_PATH):
            raise FileNotFoundError(
                f"No index found at {INDEX_PATH}. Run `python rag/build_index.py` first."
            )
        with open(INDEX_PATH, "rb") as f:
            _index_cache = pickle.load(f)
    return _index_cache


def retrieve(query: str, top_k: int = 2, min_score: float = 0.05) -> list[dict]:
    """
    Return the top_k most relevant doc chunks for a given query.

    Args:
        query: typically an error message or a plain-English question
        top_k: how many chunks to return
        min_score: chunks scoring below this cosine similarity are dropped
                   (avoids injecting irrelevant docs when nothing matches well)

    Returns:
        List of dicts: [{"text": ..., "source": ..., "score": ...}, ...]
        sorted by relevance, highest first. Empty list if nothing matches
        well enough.
    """
    index = _load_index()
    vectorizer = index["vectorizer"]
    matrix = index["matrix"]
    chunks = index["chunks"]

    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in ranked[:top_k]:
        if score < min_score:
            continue
        results.append({
            "text": chunks[idx]["text"],
            "source": chunks[idx]["source"],
            "score": float(score),
        })
    return results


def format_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks into a block suitable for inserting into an LLM prompt."""
    if not chunks:
        return ""
    parts = ["Relevant documentation:"]
    for c in chunks:
        parts.append(f"\n(from {c['source']}, relevance={c['score']:.2f})\n{c['text']}")
    return "\n".join(parts)
