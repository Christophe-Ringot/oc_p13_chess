from collections.abc import Iterator

from mistralai.client import Mistral
from mistralai.client.errors import MistralError

from app.config import settings


class RagAnswerError(Exception):
    """Erreur lors de la generation de la reponse par le LLM."""


def _client() -> Mistral:
    if not settings.mistral_api_key:
        raise RagAnswerError(
            "Aucune cle API Mistral configuree. Renseignez MISTRAL_API_KEY "
            "(cle gratuite sur https://console.mistral.ai/api-keys)."
        )
    return Mistral(
        api_key=settings.mistral_api_key,
        timeout_ms=int(settings.mistral_timeout * 1000),
    )


def _build_prompt(query: str, results: list[dict], videos: list[dict]) -> str:
    if results:
        context = "\n\n".join(
            f"- ({r.get('opening') or 'source inconnue'}) {r['text']}" for r in results
        )
    else:
        context = "Aucun extrait pertinent trouve dans la base de connaissances."

    video_titles = "\n".join(f"- {v['title']} ({v.get('channel') or 'chaine inconnue'})" for v in videos[:3])
    videos_block = f"Videos disponibles :\n{video_titles}\n\n" if video_titles else ""

    return (
        f"Ouverture etudiee : {query}\n\n"
        f"Extraits de la base de connaissances (Wikichess) :\n{context}\n\n"
        f"{videos_block}"
        "En t'appuyant uniquement sur les extraits ci-dessus, redige une reponse "
        "tres concise (3 phrases maximum, 80 mots maximum au total) pour un joueur "
        "intermediaire, sans introduction ni conclusion generique : "
        "1) l'idee strategique en une phrase, 2) un plan type en une phrase, "
        "3) un piege ou une erreur a eviter en une phrase. "
        "Va droit au but, pas de liste a puces, pas de repetition du nom de l'ouverture "
        "a chaque phrase. Si les extraits ne suffisent pas pour repondre, dis-le "
        "en une phrase plutot que d'inventer une explication."
    )


def stream_answer(query: str, results: list[dict], videos: list[dict]) -> Iterator[str]:
    prompt = _build_prompt(query, results, videos)
    try:
        stream = _client().chat.stream(
            model=settings.mistral_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=180,
        )
        for event in stream:
            content = event.data.choices[0].delta.content
            if isinstance(content, str) and content:
                yield content
    except MistralError as exc:
        raise RagAnswerError(f"Appel au LLM echoue : {exc}") from exc
    except Exception as exc:
        raise RagAnswerError(f"Appel au LLM echoue : {exc}") from exc
