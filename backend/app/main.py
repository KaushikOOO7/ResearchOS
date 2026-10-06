"""
ResearchOS API entry point.

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analysis, health, research
from app.config import settings
from app.utils.logging_setup import configure_logging, describe_secret, get_logger
from app.version import VERSION

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log a startup summary (never logging secrets)."""
    configure_logging(settings.log_level)
    logger.info("ResearchOS backend starting (version %s)", VERSION)
    logger.info("Environment: %s", settings.environment)
    logger.info("Providers: %s", ", ".join(
        name for name, enabled in settings.public_summary()["providers"].items() if enabled
    ))
    logger.info("Gemini API key: %s", describe_secret(settings.gemini_api_key))
    logger.info("Gemini model: %s", settings.gemini_model or "not set")
    logger.info("Listening port: %s (override with PORT)", settings.port)
    if not settings.gemini_api_key:
        logger.info(
            "AI analysis is disabled until GEMINI_API_KEY is set in backend/.env"
        )
    yield
    logger.info("ResearchOS backend stopped")


def create_app() -> FastAPI:
    """Build the FastAPI application (factory keeps tests isolated)."""
    app = FastAPI(
        title="ResearchOS API",
        description=(
            "AI Research Intelligence Platform — multi-source literature search, "
            "explainable ranking, and structured AI paper analysis."
        ),
        version=VERSION,
        lifespan=lifespan,
    )

    # --- CORS ----------------------------------------------------------
    # Production origins come from CORS_ORIGINS; CORS_ORIGIN_REGEX covers
    # ephemeral preview/dev hosts (e.g. *.e2b.app) without wildcarding.
    allow_origin_regex = settings.cors_origin_regex or None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # --- Routers -------------------------------------------------------
    # Every route is exposed twice: at the root (/research) and under /api
    # (/api/research). Deployments differ (Render services, reverse proxies,
    # serverless rewrites), and both path styles are documented in the README.
    for router in (health.router, research.router, analysis.router):
        app.include_router(router)
        app.include_router(router, prefix="/api")

    # --- Root ----------------------------------------------------------
    def _service_info() -> dict:
        return {
            "status": "healthy",
            "service": "ResearchOS API",
            "project": "ResearchOS",
            "description": "AI Research Intelligence Platform",
            "version": VERSION,
            "environment": settings.environment,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "endpoints": {
                "root": "GET /",
                "health": "GET /health  (alias: GET /api/health)",
                "research": "POST /research  (alias: POST /api/research)",
                "analyze": "POST /analyze-paper  (alias: POST /api/analyze-paper)",
                "paper": "GET /papers/{paper_id}",
            },
        }

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return _service_info()

    @app.get("/api", tags=["meta"], include_in_schema=False)
    def api_root() -> dict:
        return _service_info()

    # --- Error handling ------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", [])[1:]) or "request"
        message = f"Invalid request: {field} — {first.get('msg', 'invalid value')}"
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "code": "validation_error",
                "message": message,
                "retryable": False,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to the server log; the client gets a friendly message.
        logger.error("Unhandled error on %s: %s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "code": "internal_error",
                "message": "Something went wrong on the server. Please try again.",
                "retryable": True,
            },
        )

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    # Local convenience runner. Production must use:
    #   uvicorn app.main:app --host 0.0.0.0 --port $PORT
    import os

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", str(settings.port))),
        reload=os.getenv("ENVIRONMENT", "development") == "development",
    )
