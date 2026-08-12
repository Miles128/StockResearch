"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from stockresearch.api.rate_limit import limiter
from stockresearch.api.routes import (
    action_center,
    advisor,
    alerts,
    announcements,
    briefing,
    chat,
    glossary,
    market,
    news,
    portfolio,
    predictions,
    research,
    research_reports,
    risk,
    settings,
)
from stockresearch.core.config import get_settings
from stockresearch.core.constants import DISCLAIMER
from stockresearch.core.data_source_config import (
    clear_data_source_context,
    set_bocha_api_key,
    set_tushare_token,
)
from stockresearch.core.exceptions import (
    AgentError,
    DataProviderError,
    LLMConfigError,
    NotFoundError,
    StockResearchError,
    ValidationError,
)
from stockresearch.db.session import init_db
from stockresearch.services.briefing_scheduler import get_scheduler
from stockresearch.services.price_alert_scheduler import get_price_alert_scheduler
from stockresearch.services.scheduler_lock import scheduler_lock

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WEB_DIST = _PROJECT_ROOT / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    init_db()
    from stockresearch.db.session import SessionLocal
    from stockresearch.services.local_user import get_or_create_mvp_user

    db = SessionLocal()
    try:
        get_or_create_mvp_user(db)
    finally:
        db.close()
    settings = get_settings()
    if getattr(settings, "use_mock_llm", False) and not getattr(settings, "llm_api_key", ""):
        # Mock 模式下 LLM 输出为固定假内容，必须在启动日志显式警告，
        # 避免用户误把假研报当真实分析。
        logging.warning(
            "USE_MOCK_LLM=true：LLM 输出为演示假内容，不是真实分析。"
            "配置 LLM_API_KEY 并设 USE_MOCK_LLM=false 后才会执行真实研究。"
        )
    elif not getattr(settings, "use_mock_llm", True) and not getattr(settings, "llm_api_key", ""):
        logging.warning("USE_MOCK_LLM=false 但未配置 LLM_API_KEY：LLM 调用将返回未配置错误。")
    if not settings.run_schedulers_in_api:
        # Schedulers belong to the separate worker process; do NOT grab the
        # cross-process scheduler lock here, otherwise the worker can never
        # acquire it and scheduled jobs (briefings / price alerts / daily bars)
        # silently never run.
        yield
        return
    with scheduler_lock() as lock_acquired:
        if not lock_acquired:
            logging.warning(
                "Schedulers disabled in API: another process holds the scheduler lock. "
                "Run schedulers in only one process (worker OR API, not both)."
            )
        else:
            get_scheduler().start()
            get_price_alert_scheduler().start()
        try:
            yield
        finally:
            if lock_acquired:
                get_price_alert_scheduler().shutdown()
                get_scheduler().shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="StockResearch", version="0.1.0", lifespan=lifespan)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        cast(Callable[[Request, Exception], Response], _rate_limit_exceeded_handler),
    )
    app.add_middleware(SlowAPIMiddleware)

    # CORS — restrict origins in production.
    # 浏览器规范禁止 allow_origins=["*"] 与 allow_credentials=True 同时使用，
    # 因此未配置 cors_allowed_origins 时回退到本机开发常用源（而非通配 *）。
    cfg = get_settings()
    if cfg.cors_allowed_origins:
        allowed_origins = [o.strip() for o in cfg.cors_allowed_origins.split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def bind_data_source_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        set_tushare_token(request.headers.get("X-Tushare-Token"))
        set_bocha_api_key(request.headers.get("X-Bocha-Api-Key"))
        try:
            return await call_next(request)
        finally:
            clear_data_source_context()

    @app.exception_handler(StockResearchError)
    async def stockresearch_exception_handler(
        _request: Request, exc: StockResearchError
    ) -> JSONResponse:
        if isinstance(exc, NotFoundError):
            status = 404
            code = "not_found"
        elif isinstance(exc, ValidationError):
            status = 422
            code = "validation_error"
        elif isinstance(exc, LLMConfigError):
            status = 503
            code = "llm_not_configured"
        elif isinstance(exc, DataProviderError):
            status = 502
            code = "data_provider_failed"
        elif isinstance(exc, AgentError):
            status = 500
            code = "agent_failed"
        else:
            status = 400
            code = "stockresearch_error"
        return JSONResponse(
            status_code=status,
            content={"detail": str(exc), "code": code},
        )

    @app.get("/health")
    def health() -> dict[str, object]:
        """进程存活 + 基础依赖探测（SQLite 连接/迁移状态）。"""
        checks: dict[str, object] = {}
        try:
            from stockresearch.db.session import SessionLocal

            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception as exc:  # noqa: BLE001 — health 探针必须吞掉任何失败
            logging.warning("health db probe failed: %s", exc)
            checks["db"] = "error"
        return {"status": "ok", "db": checks["db"], "disclaimer": DISCLAIMER}

    @app.get("/api/v1")
    def api_index() -> dict[str, object]:
        endpoints = sorted(
            {
                str(route.path)
                for route in app.routes
                if isinstance(route, APIRoute) and route.path.startswith("/api/v1")
            }
        )
        return {
            "version": "v1",
            "endpoints": endpoints,
            "docs": "/docs",
        }

    app.include_router(portfolio.router, prefix="/api/v1")
    app.include_router(market.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(news.router, prefix="/api/v1")
    app.include_router(research.router, prefix="/api/v1")
    app.include_router(briefing.router, prefix="/api/v1")
    app.include_router(risk.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(action_center.router, prefix="/api/v1")
    app.include_router(advisor.router, prefix="/api/v1")
    app.include_router(glossary.router, prefix="/api/v1")
    app.include_router(announcements.router, prefix="/api/v1")
    app.include_router(research_reports.router, prefix="/api/v1")
    app.include_router(predictions.router, prefix="/api/v1")

    if _WEB_DIST.is_dir():
        # 拦截 /api 下的未匹配路径，返回 JSON 404 而非前端 index.html。
        # 必须在 StaticFiles 挂载之前注册，否则 /api/v1/xxx 的 404 会被 StaticFiles 吞掉。
        @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        def api_not_found(rest: str) -> dict[str, str]:
            raise NotFoundError(f"API endpoint not found: /api/{rest}")

        # 挂载前端静态资源。/api 路径已被上面的 catch-all 拦截，不会落到这里。
        app.mount(
            "/",
            StaticFiles(directory=str(_WEB_DIST), html=True),
            name="frontend",
        )
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
