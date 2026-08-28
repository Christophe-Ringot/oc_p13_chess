import chess


class InvalidFEN(Exception):
    """Levee quand une chaine FEN n'est pas valide."""


def parse_fen(fen):
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise InvalidFEN(f"FEN invalide : {exc}") from exc

    if not board.is_valid():
        raise InvalidFEN("La position FEN n'est pas legale.")

    return board


def legal_moves_uci(board):
    return [move.uci() for move in board.legal_moves]
