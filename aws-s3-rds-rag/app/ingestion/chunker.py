"""Configurable character-based chunking with overlap and natural boundaries."""

from dataclasses import dataclass

_SEPARATORS = ("\n\n", "\n", ". ", " ")


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    start_char: int
    end_char: int


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    n = len(text)
    chunks: list[TextChunk] = []
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window_start = start + max(chunk_size // 2, chunk_overlap + 1)
            for sep in _SEPARATORS:
                idx = text.rfind(sep, window_start, end)
                if idx != -1:
                    end = idx + len(sep)
                    break

        raw = text[start:end]
        stripped_left = raw.lstrip()
        piece_start = start + (len(raw) - len(stripped_left))
        piece = stripped_left.rstrip()
        if piece:
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content=piece,
                    start_char=piece_start,
                    end_char=piece_start + len(piece),
                )
            )
        if end >= n:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks
