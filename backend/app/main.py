from fastapi import FastAPI

from app.config import settings
from app.routers import chess_agent

app = FastAPI(title=settings.app_name)

app.include_router(chess_agent.router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get(f"{settings.api_prefix}/healthcheck")
def healthcheck():
    return {"status": "ok"}
