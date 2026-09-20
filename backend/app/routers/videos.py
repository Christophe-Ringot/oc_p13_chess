from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.schemas import VideoSearchResponse
from app.services.youtube import YoutubeError, get_youtube_service

router = APIRouter(tags=["videos"])


@router.get("/videos/{opening}", response_model=VideoSearchResponse)
def search_videos(
    opening: str,
    max_results: int = Query(default=settings.youtube_max_results, ge=1, le=10),
):
    try:
        videos = get_youtube_service().search_opening_videos(opening, max_results=max_results)
    except YoutubeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return VideoSearchResponse(opening=opening, videos=videos)
