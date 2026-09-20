import socket
from functools import lru_cache

import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings


class YoutubeError(Exception):
    """Erreur lors de l'appel a l'API YouTube Data v3."""


class YoutubeService:
    def __init__(
        self,
        api_key: str | None = None,
        max_results: int | None = None,
        min_view_count: int | None = None,
        timeout: float | None = None,
    ):
        self.api_key = api_key if api_key is not None else settings.youtube_api_key
        self.max_results = max_results or settings.youtube_max_results
        self.min_view_count = (
            min_view_count if min_view_count is not None else settings.youtube_min_view_count
        )
        self.timeout = timeout if timeout is not None else settings.youtube_timeout

    @property
    def client(self):
        if not self.api_key:
            raise YoutubeError(
                "Aucune cle API YouTube configuree. Renseignez YOUTUBE_API_KEY."
            )
        return build(
            "youtube",
            "v3",
            developerKey=self.api_key,
            cache_discovery=False,
            http=httplib2.Http(timeout=self.timeout),
        )

    def _fetch_view_counts(self, video_ids: list[str]) -> dict[str, int]:
        if not video_ids:
            return {}

        try:
            response = self.client.videos().list(
                part="statistics", id=",".join(video_ids)
            ).execute()
        except socket.timeout as exc:
            raise YoutubeError(f"Delai depasse (> {self.timeout}s) lors de l'appel a YouTube.") from exc
        except HttpError as exc:
            raise YoutubeError(f"Appel a l'API YouTube echoue : {exc}") from exc

        counts = {}
        for item in response.get("items", []):
            try:
                counts[item["id"]] = int(item.get("statistics", {}).get("viewCount", 0))
            except (TypeError, ValueError):
                counts[item["id"]] = 0
        return counts

    def search_opening_videos(self, opening: str, max_results: int | None = None) -> list[dict]:
        limit = max_results or self.max_results
        query = f"{opening} chess opening tutorial explanation"

        try:
            response = (
                self.client.search()
                .list(
                    q=query,
                    part="snippet",
                    type="video",
                    maxResults=limit,
                    relevanceLanguage="en",
                    safeSearch="strict",
                    videoEmbeddable="true",
                )
                .execute()
            )
        except socket.timeout as exc:
            raise YoutubeError(f"Delai depasse (> {self.timeout}s) lors de l'appel a YouTube.") from exc
        except HttpError as exc:
            status = exc.resp.status if exc.resp is not None else None
            if status == 403:
                raise YoutubeError(
                    "Quota API YouTube depasse ou cle invalide (403)."
                ) from exc
            raise YoutubeError(f"Appel a l'API YouTube echoue : {exc}") from exc

        items = [
            item
            for item in response.get("items", [])
            if item.get("id", {}).get("videoId") and item.get("snippet", {}).get("title")
        ]
        view_counts = self._fetch_view_counts([item["id"]["videoId"] for item in items])

        videos = []
        for item in items:
            video_id = item["id"]["videoId"]
            view_count = view_counts.get(video_id, 0)
            if view_count < self.min_view_count:
                continue

            snippet = item["snippet"]
            thumbnails = snippet.get("thumbnails", {})
            videos.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title"),
                    "channel": snippet.get("channelTitle"),
                    "description": snippet.get("description"),
                    "published_at": snippet.get("publishedAt"),
                    "thumbnail_url": (thumbnails.get("medium") or {}).get("url"),
                    "view_count": view_count,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "embed_url": f"https://www.youtube.com/embed/{video_id}",
                }
            )

        videos.sort(key=lambda v: v["view_count"], reverse=True)
        return videos


@lru_cache
def get_youtube_service() -> YoutubeService:
    return YoutubeService()
