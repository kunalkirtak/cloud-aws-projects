"""RAG query endpoint."""

import logging

from fastapi import APIRouter, Depends

from app.api.deps import get_generator, get_settings, get_vector_search
from app.config import Settings
from app.generation.service import GenerationService
from app.retrieval.vector_search import VectorSearch
from app.schemas.rag import QueryRequest, QueryResponse, SourceOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    settings: Settings = Depends(get_settings),
    search: VectorSearch = Depends(get_vector_search),
    generator: GenerationService = Depends(get_generator),
):
    top_k = request.top_k or settings.default_top_k
    chunks = search.search(request.question, top_k=top_k, document_id=request.document_id)
    chunks = [c for c in chunks if c.score >= settings.min_similarity_score]

    result = generator.generate(request.question, chunks)
    logger.info("rag query answered sources=%d mode=%s", len(chunks), result.mode)

    return QueryResponse(
        question=request.question,
        answer=result.answer,
        generation_mode=result.mode,
        sources=[
            SourceOut(
                document_id=c.document_id,
                title=c.title,
                source=c.source,
                chunk_id=c.chunk_id,
                chunk_index=c.chunk_index,
                score=round(c.score, 4),
                snippet=c.content[:300],
            )
            for c in chunks
        ],
    )
