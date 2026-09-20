"""Knowledge base loading and a small TF-IDF style retrieval engine.

This module implements information retrieval from first principles
(tokenization, stop-word removal, term frequency / inverse document
frequency weighting, vectorization, and cosine similarity) without
depending on a paid LLM API or a heavyweight ML framework.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "for", "of",
    "to", "in", "on", "at", "by", "with", "is", "are", "was", "were", "be",
    "been", "being", "it", "its", "this", "that", "these", "those", "as",
    "from", "into", "about", "what", "which", "who", "whom", "how", "why",
    "when", "where", "do", "does", "did", "can", "could", "should", "would",
    "will", "shall", "i", "you", "he", "she", "we", "they", "them", "their",
    "our", "your", "my", "me", "us", "not", "no", "so", "than", "too",
    "very", "just", "also", "up", "down", "out", "over", "under", "again",
    "further", "there", "here",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercase text, extract alphanumeric tokens, and drop stop words."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [token for token in tokens if token not in STOP_WORDS and len(token) > 1]


@dataclass(frozen=True)
class Document:
    """A single knowledge base document."""

    id: str
    title: str
    content: str


class KnowledgeBase:
    """Loads documents from JSON and builds a TF-IDF vector index for retrieval."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.documents: List[Document] = []
        self._doc_tokens: List[List[str]] = []
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._doc_vectors: List[Dict[str, float]] = []
        self._load()
        self._build_index()

    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Knowledge base file not found: {self.path}")

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Knowledge base file is not valid JSON: {exc}") from exc

        if not isinstance(raw, list) or not raw:
            raise ValueError("Knowledge base JSON must be a non-empty list of documents")

        documents: List[Document] = []
        for entry in raw:
            for field in ("id", "title", "content"):
                if field not in entry:
                    raise ValueError(f"Knowledge base entry missing required field '{field}': {entry}")
            documents.append(Document(id=entry["id"], title=entry["title"], content=entry["content"]))

        self.documents = documents
        logger.info("Loaded %d knowledge base document(s) from %s", len(documents), self.path)

    def _build_index(self) -> None:
        self._doc_tokens = [tokenize(f"{doc.title} {doc.content}") for doc in self.documents]

        vocab: Dict[str, int] = {}
        for tokens in self._doc_tokens:
            for token in set(tokens):
                vocab.setdefault(token, len(vocab))
        self._vocab = vocab

        num_docs = len(self.documents)
        doc_frequency: Dict[str, int] = {term: 0 for term in vocab}
        for tokens in self._doc_tokens:
            for term in set(tokens):
                doc_frequency[term] += 1

        # Smoothed IDF, similar to scikit-learn's default TF-IDF formula.
        self._idf = {
            term: math.log((1 + num_docs) / (1 + freq)) + 1.0
            for term, freq in doc_frequency.items()
        }

        self._doc_vectors = [self._vectorize(tokens) for tokens in self._doc_tokens]
        logger.info("Built TF-IDF index (vocabulary size=%d)", len(vocab))

    def _term_frequencies(self, tokens: List[str]) -> Dict[str, float]:
        counts: Dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        total = len(tokens) or 1
        return {term: count / total for term, count in counts.items()}

    def _vectorize(self, tokens: List[str]) -> Dict[str, float]:
        term_freq = self._term_frequencies(tokens)
        return {
            term: freq * self._idf.get(term, 0.0)
            for term, freq in term_freq.items()
            if term in self._idf
        }

    @staticmethod
    def _cosine_similarity(vector_a: Dict[str, float], vector_b: Dict[str, float]) -> float:
        if not vector_a or not vector_b:
            return 0.0
        shared_terms = set(vector_a) & set(vector_b)
        dot_product = sum(vector_a[term] * vector_b[term] for term in shared_terms)
        norm_a = math.sqrt(sum(value * value for value in vector_a.values()))
        norm_b = math.sqrt(sum(value * value for value in vector_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def search(self, question: str, top_n: int = 3) -> List[Tuple[Document, float]]:
        """Return up to top_n documents ranked by cosine similarity to the question."""
        query_vector = self._vectorize(tokenize(question))

        scored: List[Tuple[Document, float]] = [
            (doc, self._cosine_similarity(query_vector, doc_vector))
            for doc, doc_vector in zip(self.documents, self._doc_vectors)
        ]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_n]
