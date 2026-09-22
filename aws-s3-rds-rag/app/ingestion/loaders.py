"""Document loaders: TextLoader, MarkdownLoader, PDFLoader."""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.exceptions import AppError, MalformedDocumentError, UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf")


def _decode(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise MalformedDocumentError("File does not appear to be a text document")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


class DocumentLoader(ABC):
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def load(self, data: bytes) -> str:
        """Extract plain text from raw bytes."""


class TextLoader(DocumentLoader):
    extensions = (".txt",)

    def load(self, data: bytes) -> str:
        return _decode(data)


class MarkdownLoader(DocumentLoader):
    extensions = (".md",)

    def load(self, data: bytes) -> str:
        return _decode(data)


class PDFLoader(DocumentLoader):
    extensions = (".pdf",)

    def load(self, data: bytes) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover
            raise AppError("PDF support is not installed on this server") from exc
        try:
            with fitz.open(stream=data, filetype="pdf") as pdf:
                if pdf.needs_pass:
                    raise MalformedDocumentError("Encrypted PDFs are not supported")
                return "\n\n".join(page.get_text("text") for page in pdf)
        except AppError:
            raise
        except Exception as exc:
            raise MalformedDocumentError("Could not read PDF document") from exc


_LOADERS: dict[str, DocumentLoader] = {}
for _loader in (TextLoader(), MarkdownLoader(), PDFLoader()):
    for _ext in _loader.extensions:
        _LOADERS[_ext] = _loader


def get_loader(filename: str) -> DocumentLoader:
    ext = Path(filename).suffix.lower()
    loader = _LOADERS.get(ext)
    if loader is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext or 'none'}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    return loader


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    return re.sub(r"[-_]+", " ", stem).strip() or filename
