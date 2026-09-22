"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import documents, health, rag
from app.config import get_settings
from app.db.database import get_engine, init_db
from app.exceptions import AppError
from app.logging_config import configure_logging

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "application startup name=%s env=%s storage=%s embedding_backend=%s generation=%s",
        settings.app_name,
        settings.environment,
        settings.storage_backend,
        settings.embedding_backend,
        settings.generation_provider,
    )
    try:
        init_db(get_engine())
        logger.info("database initialized")
    except Exception as exc:  # do not crash: /health will report the problem
        logger.error("database initialization failed error_type=%s", type(exc).__name__)
    yield
    logger.info("application shutdown")


_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    description="RAG application using S3 (or local storage), PostgreSQL + pgvector and FastAPI.",
    lifespan=lifespan,
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    log = logger.error if exc.status_code >= 500 else logger.warning
    log("request failed path=%s code=%s status=%s", request.url.path, exc.code, exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [
        {"loc": [str(p) for p in e.get("loc", [])], "msg": str(e.get("msg", "")), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Invalid request", "details": details}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Internal server error"}},
    )


app.include_router(health.router)
app.include_router(documents.router)
app.include_router(rag.router)
