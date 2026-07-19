"""
build_index.py
---------------
Phase 6: builds a searchable index over the docs/ corpus.

WHY TF-IDF INSTEAD OF DENSE EMBEDDINGS (e.g. sentence-transformers + FAISS):
Dense embeddings need a large model (PyTorch-based, often 500MB-2GB) which
is heavy to install and run just for a small, technical documentation
corpus. For matching ERROR MESSAGES and API names (e.g. "KeyError",
"groupby", "to_datetime") against docs, exact keyword overlap is often
just as effective as semantic embeddings — arguably more so, since exact
term matching is exactly what you want for looking up a specific pandas
function or exception type. TF-IDF + cosine similarity is lightweight
(pure scikit-learn, no large model download) and works well for this
narrow, technical use case.

If you want to swap in real dense embeddings later, only this file and
retriever.py need to change — the rest of the app is unaffected.

Run this script once (and again any time you add/edit files in docs/):
    python rag/build_index.py
"""

import os
import re
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
INDEX_PATH = os.path.join(os.path.dirname(__file__), "index.pkl")


def chunk_markdown(text: str, source: str) -> list[dict]:
    """
    Split a markdown file into chunks along its '## ' headers.
    Each chunk keeps its header as context, since headers usually name the
    specific function/error the chunk is about (e.g. "## KeyError on column
    access") — this makes retrieval more precise than fixed-size chunking.
    """
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section or section.startswith("# "):
            # skip the top-level title-only section
            if not section.startswith("## "):
                continue
        if len(section) > 20:  # skip trivially short/empty fragments
            chunks.append({"text": section, "source": source})
    return chunks


def build_index():
    if not os.path.isdir(DOCS_DIR):
        raise FileNotFoundError(f"No docs/ folder found at {DOCS_DIR}")

    all_chunks = []
    for filename in sorted(os.listdir(DOCS_DIR)):
        if filename.endswith(".md"):
            path = os.path.join(DOCS_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            all_chunks.extend(chunk_markdown(content, source=filename))

    if not all_chunks:
        raise ValueError(f"No markdown chunks found in {DOCS_DIR}")

    texts = [c["text"] for c in all_chunks]

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),  # captures short phrases like "group by" / "key error"
        max_features=5000,
    )
    matrix = vectorizer.fit_transform(texts)

    with open(INDEX_PATH, "wb") as f:
        pickle.dump(
            {"vectorizer": vectorizer, "matrix": matrix, "chunks": all_chunks},
            f,
        )

    print(f"Indexed {len(all_chunks)} chunks from {DOCS_DIR}")
    print(f"Saved index to {INDEX_PATH}")


if __name__ == "__main__":
    build_index()
