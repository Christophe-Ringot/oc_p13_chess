from functools import lru_cache

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import settings


class VectorStoreError(Exception):
    """Erreur lors de l'utilisation de Milvus."""


class MilvusService:
    CONNECTION_ALIAS = "default"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
        embedding_dim: int | None = None,
        timeout: float | None = None,
    ):
        self.host = host or settings.milvus_host
        self.port = port or settings.milvus_port
        self.collection_name = collection_name or settings.milvus_collection
        self.embedding_dim = embedding_dim or settings.embedding_dim
        self.timeout = timeout if timeout is not None else settings.milvus_timeout

    def connect(self):
        if connections.has_connection(self.CONNECTION_ALIAS):
            return
        try:
            connections.connect(
                alias=self.CONNECTION_ALIAS,
                host=self.host,
                port=str(self.port),
                timeout=self.timeout,
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Connexion a Milvus impossible ({self.host}:{self.port}) : {exc}"
            ) from exc

    def _schema(self) -> CollectionSchema:
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4000),
            FieldSchema(name="opening", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        ]
        return CollectionSchema(fields=fields, description="Chunks Wikichess sur les ouvertures")

    def get_or_create_collection(self) -> Collection:
        self.connect()
        if utility.has_collection(self.collection_name):
            collection = Collection(self.collection_name)
        else:
            collection = Collection(name=self.collection_name, schema=self._schema())
            collection.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "AUTOINDEX",
                    "metric_type": "COSINE",
                },
            )
        collection.load()
        return collection

    def reset_collection(self) -> Collection:
        self.connect()
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
        return self.get_or_create_collection()

    def insert_chunks(
        self,
        embeddings: list[list[float]],
        texts: list[str],
        openings: list[str],
        sources: list[str],
    ) -> int:
        collection = self.get_or_create_collection()
        result = collection.insert(
            [embeddings, texts, openings, sources]
        )
        collection.flush()
        return len(result.primary_keys)

    def search(self, query_embedding: list[float], top_k: int, opening_filter: str | None = None):
        self.connect()
        if not utility.has_collection(self.collection_name):
            raise VectorStoreError(
                f"La collection Milvus '{self.collection_name}' n'existe pas. "
                "Lancez d'abord le script d'ingestion (scripts/ingest_wikichess.py)."
            )

        collection = self.get_or_create_collection()

        expr = f'opening == "{opening_filter}"' if opening_filter else None

        try:
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param={"metric_type": "COSINE"},
                limit=top_k,
                expr=expr,
                output_fields=["text", "opening", "source"],
                timeout=self.timeout,
            )
        except Exception as exc:
            raise VectorStoreError(f"Recherche Milvus echouee : {exc}") from exc

        hits = []
        for hit in results[0]:
            hits.append(
                {
                    "text": hit.entity.get("text"),
                    "opening": hit.entity.get("opening"),
                    "source": hit.entity.get("source"),
                    "score": float(hit.distance),
                }
            )
        return hits


@lru_cache
def get_vector_store() -> MilvusService:
    return MilvusService()
