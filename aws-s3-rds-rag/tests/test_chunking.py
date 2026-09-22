import pytest

from app.ingestion.chunker import chunk_text


def _sample_text(words: int = 500) -> str:
    return " ".join(f"word{i}" for i in range(words))


def test_empty_text_returns_no_chunks():
    assert chunk_text("", 200, 20) == []
    assert chunk_text("   \n  ", 200, 20) == []


def test_short_text_is_single_chunk():
    chunks = chunk_text("Just a short sentence.", 200, 20)
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].content == "Just a short sentence."


def test_chunks_respect_size_and_indexing():
    text = _sample_text()
    chunks = chunk_text(text, 200, 40)
    assert len(chunks) > 1
    assert all(len(c.content) <= 200 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunks_map_back_to_source_text():
    text = _sample_text()
    for c in chunk_text(text, 200, 40):
        assert text[c.start_char:c.end_char] == c.content


def test_chunk_overlap_is_present():
    text = _sample_text()
    chunks = chunk_text(text, 200, 40)
    for a, b in zip(chunks, chunks[1:]):
        assert b.start_char < a.end_char, "consecutive chunks must overlap"
        assert text[b.start_char:a.end_char]


def test_chunks_cover_whole_text():
    text = _sample_text()
    chunks = chunk_text(text, 200, 40)
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(text)


def test_sentence_boundaries_preferred():
    text = ("This is a sentence about storage. " * 30).strip()
    chunks = chunk_text(text, 200, 20)
    assert all(c.content.endswith(".") for c in chunks[:-1])


def test_invalid_configuration_rejected():
    with pytest.raises(ValueError):
        chunk_text("abc", 100, 100)
    with pytest.raises(ValueError):
        chunk_text("abc", 0, 0)
    with pytest.raises(ValueError):
        chunk_text("abc", 100, -1)
