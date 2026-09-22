"""Answer generation, kept separate from retrieval.

Default: ExtractiveGenerator - deterministic, no LLM. It selects the retrieved
sentences that best overlap with the question. It does NOT synthesize new text.
Optional: OpenAICompatibleGenerator - calls any OpenAI-compatible chat API.
It is disabled unless GENERATION_PROVIDER=openai_compatible.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.db.repository import RetrievedChunk
from app.exceptions import GenerationError

logger = logging.getLogger(__name__)

NO_ANSWER = "I could not find relevant information in the ingested documents."

_STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how in is it of on or that the this to was what "
    "when where which who why with you your".split()
)
_WORD = re.compile(r"[a-z0-9]+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_LEADING_MARKUP = re.compile(r"^[#>\-*\s]+")


@dataclass
class GenerationResult:
    answer: str
    mode: str
    used_llm: bool


class GenerationService(ABC):
    mode: str = "base"

    @abstractmethod
    def generate(self, question: str, chunks: list[RetrievedChunk]) -> GenerationResult:
        """Produce an answer from a question and retrieved context."""


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


def _sentences(text: str) -> list[str]:
    cleaned = (_LEADING_MARKUP.sub("", s).strip() for s in _SENT_SPLIT.split(text) if s)
    return [s for s in cleaned if s]


class ExtractiveGenerator(GenerationService):
    mode = "extractive"
    max_sentences = 3
    max_sentence_chars = 400

    def generate(self, question: str, chunks: list[RetrievedChunk]) -> GenerationResult:
        if not chunks:
            return GenerationResult(NO_ANSWER, self.mode, False)

        q_terms = _terms(question)
        candidates: list[tuple[int, int, int, str]] = []
        for rank, chunk in enumerate(chunks, start=1):
            for pos, sentence in enumerate(_sentences(chunk.content)):
                overlap = len(q_terms & _terms(sentence))
                if overlap > 0:
                    candidates.append((-overlap, rank, pos, sentence))

        if candidates:
            candidates.sort()
            picked = candidates[: self.max_sentences]
        else:
            picked = [(0, 1, i, s) for i, s in enumerate(_sentences(chunks[0].content)[:2])]
        if not picked:
            return GenerationResult(NO_ANSWER, self.mode, False)

        picked.sort(key=lambda c: (c[1], c[2]))
        parts: list[str] = []
        seen: set[str] = set()
        for _, rank, _, sentence in picked:
            if sentence in seen:
                continue
            seen.add(sentence)
            if len(sentence) > self.max_sentence_chars:
                sentence = sentence[: self.max_sentence_chars].rstrip() + "..."
            parts.append(f"{sentence} [{rank}]")
        answer = "Based on the retrieved documents: " + " ".join(parts)
        return GenerationResult(answer, self.mode, False)


class OpenAICompatibleGenerator(GenerationService):
    mode = "llm"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, question: str, chunks: list[RetrievedChunk]) -> GenerationResult:
        if not chunks:
            return GenerationResult(NO_ANSWER, self.mode, False)
        context = "\n\n".join(f"[{i}] ({c.title}) {c.content}" for i, c in enumerate(chunks, start=1))
        messages = [
            {
                "role": "system",
                "content": (
                    "Answer the question using ONLY the provided context. Cite sources like [1]. "
                    "If the context is insufficient, say you do not know."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ]
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages, "temperature": 0.1},
                timeout=self.timeout,
            )
            response.raise_for_status()
            answer = response.json()["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError, AttributeError) as exc:
            logger.error("llm request failed error_type=%s", type(exc).__name__)
            raise GenerationError("LLM provider request failed") from exc
        return GenerationResult(answer, f"{self.mode}:{self.model}", True)


def build_generation_service(settings: Settings) -> GenerationService:
    if settings.generation_provider == "openai_compatible":
        if not (settings.llm_base_url and settings.llm_api_key and settings.llm_model):
            raise GenerationError(
                "LLM provider is selected but LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are not all set"
            )
        return OpenAICompatibleGenerator(
            settings.llm_base_url, settings.llm_api_key, settings.llm_model, settings.llm_timeout_seconds
        )
    return ExtractiveGenerator()
