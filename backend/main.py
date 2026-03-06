"""
IMUSI Backend - FastAPI application entry point.
Initializes FastAPI, includes API routers, configures database, CORS, logging, and error handling.
"""
import time
from pathlib import Path
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.logging_config import configure_logging, get_logger, log_exception
from app.core.exceptions import AppException
from app.api.routes import api_router
from app.db.session import SessionLocal
from app.services.import_service import import_folder
from app.services.global_songs_watcher import start_global_songs_watcher, stop_global_songs_watcher

logger = get_logger(__name__)


def _auto_import_global_songs() -> None:
    settings = get_settings()
    if not settings.AUTO_IMPORT_GLOBAL_SONGS_ON_STARTUP:
        logger.info("Startup global song import disabled by config")
        return

    songs_dir = Path(settings.GLOBAL_SONGS_DIR).expanduser().resolve()
    if not songs_dir.is_dir():
        logger.info("Startup global song import skipped: directory not found", extra={"songs_dir": str(songs_dir)})
        return

    db = SessionLocal()
    try:
        imported, folder = import_folder(db, str(songs_dir), create_folder_record=True)
        db.commit()
        logger.info(
            "Startup global song import complete",
            extra={
                "songs_dir": str(songs_dir),
                "imported_count": len(imported),
                "folder_id": folder.id if folder else None,
            },
        )
    except Exception:
        db.rollback()
        logger.exception("Startup global song import failed", extra={"songs_dir": str(songs_dir)})
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: configure logging. Shutdown: optional cleanup."""
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL)
    logger.info("Application startup", extra={"log_level": settings.LOG_LEVEL})
    _auto_import_global_songs()
    if settings.GLOBAL_SONGS_WATCH_ENABLED:
        start_global_songs_watcher(
            settings.GLOBAL_SONGS_DIR,
            interval_seconds=settings.GLOBAL_SONGS_WATCH_INTERVAL_SECONDS,
        )
    yield
    stop_global_songs_watcher()
    logger.info("Application shutdown")


def create_application() -> FastAPI:
    settings = get_settings()
    rate_limit_window = max(1, settings.RATE_LIMIT_WINDOW_SECONDS)
    rate_limit_requests = max(1, settings.RATE_LIMIT_REQUESTS)
    rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
    auth_rate_limit_window = max(1, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS)
    auth_rate_limit_requests = max(1, settings.AUTH_RATE_LIMIT_REQUESTS)
    auth_rate_limit_paths = set(settings.AUTH_RATE_LIMIT_PATHS)
    auth_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
    rate_limit_lock = Lock()
    exempt_paths = tuple(settings.RATE_LIMIT_EXEMPT_PATHS)

    app = FastAPI(
        title="IMUSI API",
        description="Backend for IMUSI local music player mobile app",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS: allow React Native and local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware: log method, path, status, duration
    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        start = time.perf_counter()
        rate_limit_headers: dict[str, str] = {}

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_key = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_key = request.client.host
        else:
            client_key = "unknown"

        if settings.AUTH_RATE_LIMIT_ENABLED and request.url.path in auth_rate_limit_paths:
            now = time.monotonic()
            auth_bucket_key = f"{request.url.path}:{client_key}"
            with rate_limit_lock:
                bucket = auth_rate_limit_buckets[auth_bucket_key]
                cutoff = now - auth_rate_limit_window
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()

                if len(bucket) >= auth_rate_limit_requests:
                    reset_after = max(1, int(auth_rate_limit_window - (now - bucket[0])))
                    logger.warning(
                        "%s %s -> 429 auth rate limit",
                        request.method,
                        request.url.path,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Too many authentication attempts",
                            "code": "AUTH_RATE_LIMIT_EXCEEDED",
                        },
                        headers={
                            "Retry-After": str(reset_after),
                            "X-RateLimit-Limit": str(auth_rate_limit_requests),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(reset_after),
                        },
                    )
                bucket.append(now)

        if settings.RATE_LIMIT_ENABLED and not request.url.path.startswith(exempt_paths):
            now = time.monotonic()
            with rate_limit_lock:
                bucket = rate_limit_buckets[client_key]
                cutoff = now - rate_limit_window
                while bucket and bucket[0] <= cutoff:
                    bucket.popleft()

                if len(bucket) >= rate_limit_requests:
                    reset_after = max(1, int(rate_limit_window - (now - bucket[0])))
                    rate_limit_headers = {
                        "Retry-After": str(reset_after),
                        "X-RateLimit-Limit": str(rate_limit_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_after),
                    }
                    duration_ms = (time.perf_counter() - start) * 1000
                    logger.warning(
                        "%s %s -> 429 (%.1fms)",
                        request.method,
                        request.url.path,
                        duration_ms,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded",
                            "code": "RATE_LIMIT_EXCEEDED",
                        },
                        headers=rate_limit_headers,
                    )

                bucket.append(now)
                reset_after = max(1, int(rate_limit_window - (now - bucket[0])))
                rate_limit_headers = {
                    "X-RateLimit-Limit": str(rate_limit_requests),
                    "X-RateLimit-Remaining": str(max(0, rate_limit_requests - len(bucket))),
                    "X-RateLimit-Reset": str(reset_after),
                }

        response = await call_next(request)
        for header_name, header_value in rate_limit_headers.items():
            response.headers[header_name] = header_value

        duration_ms = (time.perf_counter() - start) * 1000
        log_msg = f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)"
        if response.status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        return response

    @app.get("/", include_in_schema=False)
    def root_redirect():
        return RedirectResponse(url="/docs", status_code=307)

    # Exception handlers for consistent error responses
    @app.exception_handler(AppException)
    def app_exception_handler(request: Request, exc: AppException):
        logger.warning(
            "AppException: %s (code=%s, status=%s)",
            exc.message,
            exc.code,
            exc.status_code,
            extra={"code": exc.code, "status_code": exc.status_code, "details": exc.details},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                **(exc.details or {}),
            },
        )

    @app.exception_handler(HTTPException)
    def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning("HTTPException: %s (status=%s)", exc.detail, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "code": "HTTP_ERROR",
            },
        )

    @app.exception_handler(RequestValidationError)
    def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning("Validation error: %s", exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "code": "VALIDATION_ERROR",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    def unhandled_exception_handler(request: Request, exc: Exception):
        log_exception(logger, "Unhandled exception", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "code": "INTERNAL_ERROR",
            },
        )

    # Include all API routes under API_V1_PREFIX
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
