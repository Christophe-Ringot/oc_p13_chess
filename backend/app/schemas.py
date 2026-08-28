from pydantic import BaseModel


class OpeningMove(BaseModel):
    uci: str | None = None
    san: str | None = None
    games: int = 0
    white: int = 0
    draws: int = 0
    black: int = 0
    average_rating: int | None = None


class Opening(BaseModel):
    eco: str | None = None
    name: str | None = None


class MovesResponse(BaseModel):
    fen: str
    database: str
    opening: Opening | None = None
    total_games: int = 0
    theoretical: bool
    moves: list[OpeningMove] = []


class EvaluateResponse(BaseModel):
    fen: str
    score_type: str | None = None 
    score: int | None = None
    best_move: str | None = None
    depth: int
    side_to_move: str
