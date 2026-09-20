import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.embeddings import get_embedding_service
from app.services.rag_metrics import hit_at_k, mrr, ndcg_at_k, recall_at_k
from app.services.vector_store import get_vector_store

DATASET_PATH = Path(__file__).resolve().parent / "rag_eval_dataset.json"


def load_dataset() -> list[dict]:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def count_relevant(vector_store, opening: str) -> int:
    """Nombre total de chunks indexes pour cette ouverture (verite terrain)."""
    collection = vector_store.get_or_create_collection()
    rows = collection.query(expr=f'opening == "{opening}"', output_fields=["id"], limit=10000)
    return len(rows)


def _avg(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows) if rows else 0.0


def evaluate(top_k: int, k_values: list[int]) -> dict:
    dataset = load_dataset()
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()

    relevant_counts: dict[str, int] = {}
    per_query = []

    for item in dataset:
        query, expected_opening = item["query"], item["opening"]
        if expected_opening not in relevant_counts:
            relevant_counts[expected_opening] = count_relevant(vector_store, expected_opening)
        total_relevant = relevant_counts[expected_opening]

        embedding = embedding_service.embed_query(query)
        hits = vector_store.search(query_embedding=embedding, top_k=top_k)
        relevances = [hit["opening"] == expected_opening for hit in hits]

        row = {"query": query, "opening": expected_opening, "mrr": mrr(relevances)}
        for k in k_values:
            row[f"hit@{k}"] = hit_at_k(relevances, k)
            row[f"recall@{k}"] = recall_at_k(relevances, k, total_relevant)
            row[f"ndcg@{k}"] = ndcg_at_k(relevances, k, total_relevant)
        per_query.append(row)

    aggregate = {"mrr": _avg(per_query, "mrr")}
    for k in k_values:
        aggregate[f"hit@{k}"] = _avg(per_query, f"hit@{k}")
        aggregate[f"recall@{k}"] = _avg(per_query, f"recall@{k}")
        aggregate[f"ndcg@{k}"] = _avg(per_query, f"ndcg@{k}")

    return {"per_query": per_query, "aggregate": aggregate, "num_queries": len(dataset)}


def print_report(report: dict, k_values: list[int]) -> None:
    print(f"\n{report['num_queries']} requetes evaluees\n")

    header = ["requete", "ouverture attendue"] + [f"hit@{k}" for k in k_values] + ["mrr"]
    print(" | ".join(header))
    for row in report["per_query"]:
        values = (
            [row["query"][:45], row["opening"]]
            + [f"{row[f'hit@{k}']:.0f}" for k in k_values]
            + [f"{row['mrr']:.2f}"]
        )
        print(" | ".join(values))

    print("\n--- Moyennes ---")
    agg = report["aggregate"]
    for k in k_values:
        print(
            f"K={k:>2}  Hit@K={agg[f'hit@{k}']:.2f}  "
            f"Recall@K={agg[f'recall@{k}']:.2f}  NDCG@K={agg[f'ndcg@{k}']:.2f}"
        )
    print(f"MRR global = {agg['mrr']:.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top-k", type=int, default=10, help="Nombre de resultats recuperes par requete."
    )
    parser.add_argument(
        "--k-values", default="1,3,5", help="Valeurs de K a evaluer, separees par des virgules."
    )
    parser.add_argument("--json", default=None, help="Chemin de sortie pour le rapport JSON complet.")
    args = parser.parse_args()

    k_values = sorted({int(k) for k in args.k_values.split(",")})
    top_k = max(args.top_k, max(k_values))

    report = evaluate(top_k=top_k, k_values=k_values)
    print_report(report, k_values)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nRapport complet ecrit dans {args.json}")


if __name__ == "__main__":
    main()
