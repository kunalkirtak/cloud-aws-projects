"""Chatbot orchestration: retrieval + answer construction + source attribution."""
from __future__ import annotations

import logging
from typing import List, Tuple

from app.config import settings
from app.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Below this cosine similarity score, a document is treated as not
# relevant enough to be used as an answer or cited as a source.
MIN_RELEVANCE_SCORE = 0.05

FALLBACK_ANSWER = (
    "I could not find a document in the knowledge base that is relevant "
    "enough to answer that question confidently. Try rephrasing, or ask "
    "about a topic covered in the knowledge base such as EC2, IAM, "
    "Security Groups, S3, RDS, ECS, Docker, FastAPI, or REST APIs."
)


class Chatbot:
    """Retrieves relevant documents and builds a structured chat response."""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base

    def answer(self, question: str) -> Tuple[str, List[dict]]:
        top_n = settings.max_results
        logger.info("Running retrieval for question (top_n=%d)", top_n)

        results = self.knowledge_base.search(question, top_n=top_n)
        relevant = [(doc, score) for doc, score in results if score >= MIN_RELEVANCE_SCORE]

        logger.info("Retrieved %d relevant document(s) out of %d candidate(s)", len(relevant), len(results))

        if not relevant:
            return FALLBACK_ANSWER, []

        best_doc, _ = relevant[0]
        sources = [
            {"id": doc.id, "title": doc.title, "score": round(score, 4)}
            for doc, score in relevant
        ]
        return best_doc.content, sources
