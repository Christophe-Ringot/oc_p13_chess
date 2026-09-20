import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import chess_agent, vector_search, videos

logger = logging.getLogger("oc_p13_chess")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erreur non geree sur %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne inattendue. Consultez les logs du backend."},
    )


app.include_router(chess_agent.router, prefix=settings.api_prefix)
app.include_router(vector_search.router, prefix=settings.api_prefix)
app.include_router(videos.router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get(f"{settings.api_prefix}/healthcheck")
def healthcheck():
    return {"status": "ok"}
