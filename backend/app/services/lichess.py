import httpx
from app.config import settings

USER_AGENT = "oc-p13-chess-agent"

class LichessError(Exception):
    """Erreur lors d'un appel a l'API Lichess (indisponible, timeout, quota...)."""


class LichessService:

    def __init__(self, base_url=None, database=None, timeout=None, token=None):
        self.base_url = (base_url or settings.lichess_explorer_url).rstrip("/")
        self.database = database or settings.lichess_database
        self.timeout = timeout if timeout is not None else settings.lichess_timeout
        self.token = token if token is not None else settings.lichess_token

    def _headers(self):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_opening_moves(self, fen, database=None):
        db = database or self.database
        url = f"{self.base_url}/{db}"

        try:
            response = httpx.get(
                url,
                params={"fen": fen},
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LichessError("Delai depasse lors de l'appel a Lichess.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise LichessError(
                    "Lichess a refuse la requete (401). L'Opening Explorer exige "
                    "un jeton personnel : renseignez LICHESS_TOKEN."
                ) from exc
            if status == 429:
                raise LichessError(
                    "Limite de requetes Lichess atteinte, reessayez plus tard."
                ) from exc
            raise LichessError(
                f"Lichess a repondu avec le statut {status}."
            ) from exc
        except httpx.HTTPError as exc:
            raise LichessError(f"Appel a Lichess impossible : {exc}") from exc

        return self._normalize(response.json())

    def _normalize(self, data):
        moves = []
        for move in data.get("moves", []):
            white = move.get("white", 0)
            draws = move.get("draws", 0)
            black = move.get("black", 0)
            total = white + draws + black
            moves.append(
                {
                    "uci": move.get("uci"),
                    "san": move.get("san"),
                    "games": total,
                    "white": white,
                    "draws": draws,
                    "black": black,
                    "average_rating": move.get("averageRating"),
                }
            )

        moves = moves[: settings.lichess_top_moves]

        opening = data.get("opening")
        total_games = (
            data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
        )

        return {"opening": opening, "total_games": total_games, "moves": moves}
