"""Application exceptions that map to clean API error responses."""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidRequestError(AppError):
    status_code = 422
    code = "invalid_request"
    default_message = "Invalid request"


class InvalidQueryError(AppError):
    status_code = 422
    code = "invalid_query"
    default_message = "Invalid query"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"
    default_message = "Unsupported file type"


class EmptyDocumentError(AppError):
    status_code = 422
    code = "empty_document"
    default_message = "Document is empty"


class MalformedDocumentError(AppError):
    status_code = 422
    code = "malformed_document"
    default_message = "Document could not be read"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"
    default_message = "File is too large"


class DocumentNotFoundError(AppError):
    status_code = 404
    code = "document_not_found"
    default_message = "Document not found"


class ObjectNotFoundError(AppError):
    status_code = 404
    code = "object_not_found"
    default_message = "Object not found in storage"


class InvalidStorageKeyError(AppError):
    status_code = 400
    code = "invalid_storage_key"
    default_message = "Invalid storage key"


class StorageError(AppError):
    status_code = 502
    code = "storage_error"
    default_message = "Object storage request failed"


class DatabaseError(AppError):
    status_code = 503
    code = "database_error"
    default_message = "Database operation failed"


class EmbeddingError(AppError):
    status_code = 500
    code = "embedding_error"
    default_message = "Embedding generation failed"


class RetrievalError(AppError):
    status_code = 500
    code = "retrieval_error"
    default_message = "Retrieval failed"


class GenerationError(AppError):
    status_code = 502
    code = "generation_error"
    default_message = "Answer generation failed"


class IngestionError(AppError):
    status_code = 500
    code = "ingestion_error"
    default_message = "Ingestion failed"
