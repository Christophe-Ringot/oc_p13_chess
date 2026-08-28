from fastapi import APIRouter, HTTPException, Query
from app.chess_utils import InvalidFEN, legal_moves_uci, parse_fen
from app.schemas import EvaluateResponse, MovesResponse
from app.services.engine import EngineError, EngineService
from app.services.lichess import LichessError, LichessService

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
