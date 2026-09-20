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


class VectorSearchResult(BaseModel):
    text: str
    opening: str | None = None
    source: str | None = None
    score: float


class VideoResult(BaseModel):
    video_id: str
    title: str
    channel: str | None = None
    description: str | None = None
    published_at: str | None = None
    thumbnail_url: str | None = None
    view_count: int | None = None
    url: str
    embed_url: str


class VectorSearchResponse(BaseModel):
    query: str
    results: list[VectorSearchResult] = []
    videos: list[VideoResult] = []


class VideoSearchResponse(BaseModel):
    opening: str
    videos: list[VideoResult] = []


class Evaluation(BaseModel):
    score_type: str | None = None
    score: int | None = None
    best_move: str | None = None
    depth: int
    side_to_move: str


class AgentAnalysisResponse(BaseModel):
    fen: str
    theoretical: bool
    opening: Opening | None = None
    total_games: int = 0
    moves: list[OpeningMove] = []
    evaluation: Evaluation | None = None
    results: list[VectorSearchResult] = []
    videos: list[VideoResult] = []
    tools_used: list[str] = []


class AgentAnswerRequest(BaseModel):
    opening: str
    results: list[VectorSearchResult] = []
    videos: list[VideoResult] = []
