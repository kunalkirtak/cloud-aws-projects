"""FastAPI application entry point for the AWS EC2 AI Chatbot."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException

from app.chatbot import Chatbot
from app.config import settings
from app.knowledge_base import KnowledgeBase
from app.schemas import ChatRequest, ChatResponse, HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")

knowledge_base: Optional[KnowledgeBase] = None
chatbot: Optional[Chatbot] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the knowledge base and build the retrieval index at startup."""
    global knowledge_base, chatbot
    logger.info("Starting %s (environment=%s)", settings.app_name, settings.environment)
    try:
        knowledge_base = KnowledgeBase(settings.knowledge_base_path)
        chatbot = Chatbot(knowledge_base)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load knowledge base: %s", exc)
        raise
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="A lightweight, retrieval-based AI chatbot backend designed for AWS EC2 deployment.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def read_root() -> dict:
    """Basic service metadata."""
    return {
        "service": settings.app_name,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness/readiness check used by monitoring and load balancers."""
    doc_count = len(knowledge_base.documents) if knowledge_base else 0
    return HealthResponse(status="ok", knowledge_base_documents=doc_count)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Answer a question using TF-IDF retrieval over the knowledge base."""
    if chatbot is None:
        logger.error("Chat request received before the knowledge base was initialized")
        raise HTTPException(status_code=503, detail="Service is not ready yet.")

    logger.info("Incoming chat request: %r", request.question)
    try:
        answer_text, sources = chatbot.answer(request.question)
    except Exception:
        logger.exception("Unexpected error while answering chat request")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing the request.",
        )

    return ChatResponse(question=request.question, answer=answer_text, sources=sources)
