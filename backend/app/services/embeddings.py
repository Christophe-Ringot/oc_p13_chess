from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


class EmbeddingError(Exception):
    """Erreur lors du chargement ou de l'utilisation du modele d'embedding."""


class EmbeddingService:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise EmbeddingError(
                    f"Chargement du modele d'embedding '{self.model_name}' impossible : {exc}"
                ) from exc
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = self.model.encode(texts, normalize_embeddings=True)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"Calcul des embeddings echoue : {exc}") from exc
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        # Les modeles Qwen3-Embedding sont entraines pour la recherche
        # asymetrique : la requete doit etre encodee avec l'instruction
        # "query" (definie dans le modele) tandis que les passages restent
        # encodes bruts (embed()). Sans cette instruction, la requete et les
        # passages ne sont pas projetes de maniere optimale dans le meme
        # espace, ce qui degrade le classement (donc le Recall@K).
        kwargs = {"normalize_embeddings": True}
        if "query" in getattr(self.model, "prompts", {}):
            kwargs["prompt_name"] = "query"
        try:
            vectors = self.model.encode([text], **kwargs)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"Calcul des embeddings echoue : {exc}") from exc
        return vectors.tolist()[0]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
