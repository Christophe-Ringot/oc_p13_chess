import os
import shutil
from stockfish import Stockfish
from app.config import settings

class EngineError(Exception):
    """Erreur lors de l'utilisation du moteur Stockfish"""


class EngineService:
    def __init__(self, path=None, depth=None):
        self.path = path or settings.stockfish_path
        self.depth = depth or settings.stockfish_depth

    def _resolve_path(self):
        if os.path.isfile(self.path):
            return self.path
        found = shutil.which(self.path)
        if found:
            return found
        raise EngineError(
            f"Binaire Stockfish introuvable ({self.path}). Installez-le ou "
            "renseignez STOCKFISH_PATH."
        )

    def _engine(self):
        path = self._resolve_path()
        try:
            return Stockfish(path=path, depth=self.depth)
        except Exception as exc:  # PermissionError, binaire corrompu...
            raise EngineError(
                f"Moteur Stockfish indisponible ({path}) : {exc}"
            ) from exc

    def evaluate(self, fen):
        engine = self._engine()

        if not engine.is_fen_valid(fen):
            raise EngineError("Position FEN rejetee par Stockfish.")

        engine.set_fen_position(fen)

        evaluation = engine.get_evaluation()
        best_move = engine.get_best_move()

        return {
            "score_type": evaluation.get("type"),
            "score": evaluation.get("value"),
            "best_move": best_move,
            "depth": self.depth,
            "side_to_move": "white" if " w " in fen else "black",
        }
