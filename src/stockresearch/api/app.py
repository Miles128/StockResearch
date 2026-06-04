"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from stockresearch.api.routes import chat, market, news, portfolio, research, risk, settings
from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.exceptions import StockResearchError
from stockresearch.db.session import init_db

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WEB_DIST = _PROJECT_ROOT / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    from stockresearch.db.session import SessionLocal
    from stockresearch.services.auth import get_or_create_mvp_user

    db = SessionLocal()
    try:
        get_or_create_mvp_user(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="StockResearch", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(StockResearchError)
    async def stockresearch_exception_handler(_request: Request, exc: StockResearchError) -> JSONResponse:
        from stockresearch.core.exceptions import (
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            ValidationError,
        )

        if isinstance(exc, (AuthenticationError, AuthorizationError)):
            status = 401
        elif isinstance(exc, NotFoundError):
            status = 404
        elif isinstance(exc, ValidationError):
            status = 422
        else:
            status = 400
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "disclaimer": DISCLAIMER}

    @app.get("/api/v1")
    def api_index() -> dict[str, object]:
        return {
            "version": "v1",
            "endpoints": [
                "/api/v1/chat",
                "/api/v1/market/overview",
                "/api/v1/market/quotes",
                "/api/v1/portfolio/holdings",
                "/api/v1/news/feed",
                "/api/v1/research/analyze",
                "/api/v1/risk/checkup",
                "/api/v1/settings/llm",
                "/api/v1/settings/llm/test",
            ],
            "docs": "/docs",
        }

    app.include_router(portfolio.router, prefix="/api/v1")
    app.include_router(market.router, prefix="/api/v1")
    app.include_router(news.router, prefix="/api/v1")
    app.include_router(research.router, prefix="/api/v1")
    app.include_router(risk.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")

    if _WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="frontend")
    else:

        @app.get("/")
        def root() -> dict[str, str]:
            return {
                "app": "StockResearch",
                "message": "API 已运行。请访问前端 UI，不要直接打开后端根路径。",
                "ui_dev": "http://localhost:5174",
                "api_docs": "/docs",
                "health": "/health",
            }

    return app


app = create_app()
