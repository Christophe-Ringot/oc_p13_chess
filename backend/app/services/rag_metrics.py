import math


def hit_at_k(relevances: list[bool], k: int) -> float:
    return 1.0 if any(relevances[:k]) else 0.0


def recall_at_k(relevances: list[bool], k: int, total_relevant: int) -> float:
    if total_relevant == 0:
        return 0.0
    return sum(relevances[:k]) / total_relevant


def ndcg_at_k(relevances: list[bool], k: int, total_relevant: int) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, rel in enumerate(relevances[:k]) if rel)
    ideal_hits = min(k, total_relevant)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def mrr(relevances: list[bool]) -> float:
    for i, rel in enumerate(relevances):
        if rel:
            return 1.0 / (i + 1)
    return 0.0
