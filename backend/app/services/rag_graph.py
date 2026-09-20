import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.chess_utils import legal_moves_uci, parse_fen
from app.config import settings
from app.services.embeddings import EmbeddingError, EmbeddingService, get_embedding_service
from app.services.engine import EngineError, EngineService
from app.services.lichess import LichessError, LichessService
from app.services.vector_store import MilvusService, VectorStoreError, get_vector_store
from app.services.youtube import YoutubeError, YoutubeService, get_youtube_service


class RagState(TypedDict, total=False):
    query: str
    opening: str | None
    top_k: int

    fen: str
    database: str | None
    theoretical: bool
    opening_eco: str | None
    total_games: int
    moves: list[dict]
    evaluation: dict | None
    lichess_error: str | None
    stockfish_error: str | None
    video_error: str | None

    query_embedding: list[float]
    results: list[dict]
    videos: list[dict]
    tools_used: Annotated[list[str], operator.add]


def _lookup_opening_node(lichess_service: LichessService):

    def node(state: RagState) -> RagState:
        board = parse_fen(state["fen"])
        legal = set(legal_moves_uci(board))

        try:
            result = lichess_service.get_opening_moves(
                state["fen"], database=state.get("database")
            )
        except LichessError as exc:
            return {
                "theoretical": False,
                "opening": None,
                "opening_eco": None,
                "total_games": 0,
                "moves": [],
                "lichess_error": str(exc),
                "tools_used": ["lichess:unavailable"],
            }

        moves = [m for m in result["moves"] if m["uci"] in legal]
        opening = result.get("opening") or {}

        return {
            "theoretical": len(moves) > 0,
            "query": opening.get("name") or "",
            "opening": opening.get("name"),
            "opening_eco": opening.get("eco"),
            "total_games": result["total_games"],
            "moves": moves,
            "tools_used": ["lichess"],
        }

    return node


def _evaluate_position_node(engine_service: EngineService):

    def node(state: RagState) -> RagState:
        try:
            evaluation = engine_service.evaluate(state["fen"])
        except EngineError as exc:
            return {
                "evaluation": None,
                "stockfish_error": str(exc),
                "tools_used": ["stockfish:unavailable"],
            }
        return {"evaluation": evaluation, "tools_used": ["stockfish"]}

    return node


def _route_after_opening(state: RagState) -> Literal["theoretical", "out_of_book"]:
    if state.get("theoretical") and state.get("opening"):
        return "theoretical"
    return "out_of_book"


def _embed_query_node(embedding_service: EmbeddingService):
    def node(state: RagState) -> RagState:
        return {
            "query_embedding": embedding_service.embed_query(state["query"]),
            "tools_used": ["embeddings"],
        }

    return node


def _search_milvus_node(vector_store: MilvusService):
    def node(state: RagState) -> RagState:
        hits = vector_store.search(
            query_embedding=state["query_embedding"],
            top_k=state.get("top_k", settings.rag_top_k),
            opening_filter=state.get("opening"),
        )
        return {"results": hits, "tools_used": ["milvus"]}

    return node


def _search_videos_node(youtube_service: YoutubeService):
    def node(state: RagState) -> RagState:
        opening = state.get("opening") or state["query"]
        try:
            videos = youtube_service.search_opening_videos(opening)
        except YoutubeError as exc:
            return {"videos": [], "video_error": str(exc), "tools_used": ["youtube:unavailable"]}
        return {"videos": videos, "tools_used": ["youtube"]}

    return node


def _format_results_node(state: RagState) -> RagState:
    sorted_hits = sorted(state.get("results", []), key=lambda h: h["score"], reverse=True)
    return {"results": sorted_hits}


def build_rag_graph(
    embedding_service: EmbeddingService | None = None,
    vector_store: MilvusService | None = None,
    youtube_service: YoutubeService | None = None,
):
    embedding_service = embedding_service or get_embedding_service()
    vector_store = vector_store or get_vector_store()
    youtube_service = youtube_service or get_youtube_service()

    graph = StateGraph(RagState)
    graph.add_node("embed_query", _embed_query_node(embedding_service))
    graph.add_node("search_milvus", _search_milvus_node(vector_store))
    graph.add_node("search_videos", _search_videos_node(youtube_service))
    graph.add_node("format_results", _format_results_node)

    graph.add_edge(START, "embed_query")
    graph.add_edge("embed_query", "search_milvus")
    graph.add_edge("search_milvus", "search_videos")
    graph.add_edge("search_videos", "format_results")
    graph.add_edge("format_results", END)

    return graph.compile()


def build_position_agent_graph(
    lichess_service: LichessService | None = None,
    engine_service: EngineService | None = None,
    embedding_service: EmbeddingService | None = None,
    vector_store: MilvusService | None = None,
    youtube_service: YoutubeService | None = None,
):
    lichess_service = lichess_service or LichessService()
    engine_service = engine_service or EngineService()
    embedding_service = embedding_service or get_embedding_service()
    vector_store = vector_store or get_vector_store()
    youtube_service = youtube_service or get_youtube_service()

    graph = StateGraph(RagState)
    graph.add_node("lookup_opening", _lookup_opening_node(lichess_service))
    graph.add_node("evaluate_position", _evaluate_position_node(engine_service))
    graph.add_node("embed_query", _embed_query_node(embedding_service))
    graph.add_node("search_milvus", _search_milvus_node(vector_store))
    graph.add_node("search_videos", _search_videos_node(youtube_service))
    graph.add_node("format_results", _format_results_node)

    graph.add_edge(START, "lookup_opening")
    graph.add_edge(START, "evaluate_position")
    graph.add_edge("evaluate_position", END)

    graph.add_conditional_edges(
        "lookup_opening",
        _route_after_opening,
        {"theoretical": "embed_query", "out_of_book": END},
    )
    graph.add_edge("embed_query", "search_milvus")
    graph.add_edge("search_milvus", "search_videos")
    graph.add_edge("search_videos", "format_results")
    graph.add_edge("format_results", END)

    return graph.compile()


_rag_app = None
_position_agent = None


def get_rag_app():
    global _rag_app
    if _rag_app is None:
        _rag_app = build_rag_graph()
    return _rag_app


def get_position_agent():
    global _position_agent
    if _position_agent is None:
        _position_agent = build_position_agent_graph()
    return _position_agent


def run_vector_search(query: str, opening: str | None = None, top_k: int | None = None) -> dict:
    app = get_rag_app()
    final_state = app.invoke(
        {
            "query": query,
            "opening": opening,
            "top_k": top_k or settings.rag_top_k,
            "tools_used": [],
        }
    )
    return {
        "results": final_state.get("results", []),
        "videos": final_state.get("videos", []),
    }


def run_position_agent(fen: str, database: str | None = None, top_k: int | None = None) -> dict:
    parse_fen(fen) 

    app = get_position_agent()
    final_state = app.invoke(
        {
            "fen": fen,
            "database": database,
            "top_k": top_k or settings.rag_top_k,
            "tools_used": [],
        }
    )
    return {
        "theoretical": final_state.get("theoretical", False),
        "opening": final_state.get("opening"),
        "opening_eco": final_state.get("opening_eco"),
        "total_games": final_state.get("total_games", 0),
        "moves": final_state.get("moves", []),
        "evaluation": final_state.get("evaluation"),
        "results": final_state.get("results", []),
        "videos": final_state.get("videos", []),
        "tools_used": final_state.get("tools_used", []),
        "lichess_error": final_state.get("lichess_error"),
        "stockfish_error": final_state.get("stockfish_error"),
        "video_error": final_state.get("video_error"),
    }


_STEP_LABELS = {
    "lookup_opening": "Lichess — théorie d'ouverture",
    "evaluate_position": "Stockfish — évaluation",
    "embed_query": "Embeddings — vectorisation de la requête",
    "search_milvus": "Wikichess — recherche vectorielle (Milvus)",
    "search_videos": "YouTube — recherche de vidéos",
}


def run_position_agent_stream(fen: str, database: str | None = None, top_k: int | None = None):
    parse_fen(fen)

    app = get_position_agent()
    initial_state: RagState = {
        "fen": fen,
        "database": database,
        "top_k": top_k or settings.rag_top_k,
        "tools_used": [],
    }
    accumulated: dict = dict(initial_state)

    try:
        for chunk in app.stream(initial_state, stream_mode="updates"):
            for node_name, update in chunk.items():
                accumulated.update(update)

                if node_name == "lookup_opening":
                    ok = "lichess" in update.get("tools_used", [])
                    if ok:
                        n = len(update.get("moves", []))
                        opening = update.get("opening")
                        detail = (
                            f"{opening} : {n} coup(s) référencé(s)"
                            if opening
                            else (
                                f"{n} coup(s) référencé(s), aucune ouverture nommée"
                                if n
                                else "Position hors théorie connue"
                            )
                        )
                    else:
                        detail = accumulated.get("lichess_error") or "Lichess indisponible."
                    yield {
                        "step": "lookup_opening",
                        "label": _STEP_LABELS["lookup_opening"],
                        "status": "ok" if ok else "error",
                        "detail": detail,
                    }

                    if ok and accumulated.get("opening"):
                        yield {
                            "step": "decision_rag",
                            "label": "Décision de l'agent",
                            "status": "ok",
                            "detail": "Ouverture identifiée → consultation de Wikichess et YouTube",
                        }
                    else:
                        yield {
                            "step": "decision_rag",
                            "label": "Décision de l'agent",
                            "status": "skipped",
                            "detail": "Pas d'ouverture identifiée → Wikichess/YouTube non consultés",
                        }

                elif node_name == "evaluate_position":
                    ok = "stockfish" in update.get("tools_used", [])
                    if ok:
                        ev = update.get("evaluation") or {}
                        detail = f"Coup conseillé : {ev.get('best_move') or '—'}"
                    else:
                        detail = accumulated.get("stockfish_error") or "Stockfish indisponible."
                    yield {
                        "step": "evaluate_position",
                        "label": _STEP_LABELS["evaluate_position"],
                        "status": "ok" if ok else "error",
                        "detail": detail,
                    }

                elif node_name == "embed_query":
                    yield {
                        "step": "embed_query",
                        "label": _STEP_LABELS["embed_query"],
                        "status": "ok",
                        "detail": "Requête vectorisée",
                    }

                elif node_name == "search_milvus":
                    n = len(update.get("results", []))
                    yield {
                        "step": "search_milvus",
                        "label": _STEP_LABELS["search_milvus"],
                        "status": "ok",
                        "detail": f"{n} extrait(s) trouvé(s)",
                    }

                elif node_name == "search_videos":
                    ok = "youtube" in update.get("tools_used", [])
                    detail = (
                        f"{len(update.get('videos', []))} vidéo(s) trouvée(s)"
                        if ok
                        else (accumulated.get("video_error") or "YouTube indisponible.")
                    )
                    yield {
                        "step": "search_videos",
                        "label": _STEP_LABELS["search_videos"],
                        "status": "ok" if ok else "error",
                        "detail": detail,
                    }
    except (VectorStoreError, EmbeddingError) as exc:
        yield {
            "step": "search_milvus",
            "label": _STEP_LABELS["search_milvus"],
            "status": "error",
            "detail": str(exc),
        }

    opening_name = accumulated.get("opening")
    yield {
        "step": "done",
        "result": {
            "fen": fen,
            "theoretical": accumulated.get("theoretical", False),
            "opening": (
                {"eco": accumulated.get("opening_eco"), "name": opening_name}
                if opening_name
                else None
            ),
            "total_games": accumulated.get("total_games", 0),
            "moves": accumulated.get("moves", []),
            "evaluation": accumulated.get("evaluation"),
            "results": accumulated.get("results", []),
            "videos": accumulated.get("videos", []),
            "tools_used": accumulated.get("tools_used", []),
        },
    }
