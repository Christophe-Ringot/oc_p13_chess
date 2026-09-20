# python scripts/ingest_wikichess.py [--reset]
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.chunking import split_into_chunks 
from app.services.embeddings import get_embedding_service
from app.services.vector_store import get_vector_store


def load_articles(data_dir: Path) -> list[dict]:
    articles = []
    for path in sorted(data_dir.glob("*.txt")):
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        title = lines[0].lstrip("#").strip() if lines and lines[0].startswith("#") else path.stem
        source = ""
        for line in lines[:5]:
            if line.startswith("Source:"):
                source = line.removeprefix("Source:").strip()
                break

        articles.append({"opening": title, "source": source, "text": content})
    return articles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Supprime et recree la collection Milvus avant l'ingestion.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parent.parent / settings.wikichess_data_dir),
        help="Dossier contenant les articles Wikichess (.txt).",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    articles = load_articles(data_dir)
    if not articles:
        raise SystemExit(f"Aucun article .txt trouve dans {data_dir}")

    print(f"{len(articles)} articles trouves dans {data_dir}")

    embedding_service = get_embedding_service()
    vector_store = get_vector_store()

    if args.reset:
        print("Reinitialisation de la collection Milvus...")
        vector_store.reset_collection()
    else:
        vector_store.get_or_create_collection()

    total_chunks = 0
    for article in articles:
        chunks = split_into_chunks(
            article["text"],
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        if not chunks:
            continue

        print(f"  - {article['opening']}: {len(chunks)} chunk(s)")
        embeddings = embedding_service.embed(chunks)
        vector_store.insert_chunks(
            embeddings=embeddings,
            texts=chunks,
            openings=[article["opening"]] * len(chunks),
            sources=[article["source"]] * len(chunks),
        )
        total_chunks += len(chunks)

    print(f"Ingestion terminee : {total_chunks} chunks indexes dans '{settings.milvus_collection}'.")


if __name__ == "__main__":
    main()
