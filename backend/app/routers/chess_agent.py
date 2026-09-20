import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.chess_utils import InvalidFEN, legal_moves_uci, parse_fen
from app.schemas import AgentAnalysisResponse, EvaluateResponse, MovesResponse, Opening
from app.services.embeddings import EmbeddingError
from app.services.engine import EngineError, EngineService
from app.services.lichess import LichessError, LichessService
from app.services.rag_graph import run_position_agent, run_position_agent_stream
from app.services.vector_store import VectorStoreError

router = APIRouter(tags=["chess"])

lichess_service = LichessService()
engine_service = EngineService()


@router.get("/moves/{fen:path}", response_model=MovesResponse)
def get_moves(fen: str, database: str | None = Query(default=None)):
    try:
        board = parse_fen(fen)
    except InvalidFEN as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = lichess_service.get_opening_moves(fen, database=database)
    except LichessError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    legal = set(legal_moves_uci(board))
    moves = [m for m in result["moves"] if m["uci"] in legal]

    return MovesResponse(
        fen=fen,
        database=database or lichess_service.database,
        opening=result["opening"],
        total_games=result["total_games"],
        theoretical=len(moves) > 0,
        moves=moves,
    )


@router.get("/evaluate/{fen:path}", response_model=EvaluateResponse)
def evaluate_position(fen: str):
    try:
        parse_fen(fen)
    except InvalidFEN as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = engine_service.evaluate(fen)
    except EngineError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return EvaluateResponse(fen=fen, **result)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/agent/stream")
def analyze_position_stream(fen: str, database: str | None = Query(default=None)):
    try:
        parse_fen(fen)
    except InvalidFEN as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def event_stream():
        for event in run_position_agent_stream(fen, database=database):
            if event["step"] == "done":
                yield _sse("done", event["result"])
            else:
                yield _sse("step", event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/agent/{fen:path}", response_model=AgentAnalysisResponse)
def analyze_position(fen: str, database: str | None = Query(default=None)):
    try:
        parse_fen(fen)
    except InvalidFEN as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = run_position_agent(fen, database=database)
    except (VectorStoreError, EmbeddingError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    opening = (
        Opening(eco=result["opening_eco"], name=result["opening"])
        if result["opening"]
        else None
    )

    return AgentAnalysisResponse(
        fen=fen,
        theoretical=result["theoretical"],
        opening=opening,
        total_games=result["total_games"],
        moves=result["moves"],
        evaluation=result["evaluation"],
        results=result["results"],
        videos=result["videos"],
        tools_used=result["tools_used"],
    )
