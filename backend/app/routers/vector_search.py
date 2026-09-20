import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas import AgentAnswerRequest, VectorSearchResponse
from app.services.embeddings import EmbeddingError
from app.services.rag_answer import RagAnswerError, stream_answer
from app.services.rag_graph import run_vector_search
from app.services.vector_store import VectorStoreError

router = APIRouter(tags=["rag"])


@router.get("/vector-search", response_model=VectorSearchResponse)
def vector_search(
    opening: str = Query(..., description="Nom de l'ouverture recherchee, ex: 'Sicilian Defense'"),
    top_k: int = Query(default=settings.rag_top_k, ge=1, le=20),
):
    try:
        output = run_vector_search(query=opening, top_k=top_k)
    except (VectorStoreError, EmbeddingError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return VectorSearchResponse(query=opening, results=output["results"], videos=output["videos"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/vector-search/stream")
def vector_search_stream(
    opening: str = Query(..., description="Nom de l'ouverture recherchee, ex: 'Sicilian Defense'"),
    top_k: int = Query(default=settings.rag_top_k, ge=1, le=20),
):
    try:
        output = run_vector_search(query=opening, top_k=top_k)
    except (VectorStoreError, EmbeddingError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    def event_stream():
        yield _sse("sources", {"results": output["results"], "videos": output["videos"]})
        try:
            for chunk in stream_answer(opening, output["results"], output["videos"]):
                yield _sse("delta", {"text": chunk})
        except RagAnswerError as exc:
            yield _sse("llm_error", {"message": str(exc)})
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/agent/answer/stream")
def agent_answer_stream(payload: AgentAnswerRequest):
    results = [r.model_dump() for r in payload.results]
    videos = [v.model_dump() for v in payload.videos]

    def event_stream():
        yield _sse("sources", {"results": results, "videos": videos})
        try:
            for chunk in stream_answer(payload.opening, results, videos):
                yield _sse("delta", {"text": chunk})
        except RagAnswerError as exc:
            yield _sse("llm_error", {"message": str(exc)})
        yield _sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
