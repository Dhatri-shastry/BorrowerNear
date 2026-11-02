import logging
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mysql.connector import Error as MySQLError
from redis.exceptions import RedisError

from app.config import get_settings
from app.db import cursor
from app.routes import read, auth, borrowing
from app.routes import messaging
from app.redis_store import check_redis, close_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("borrownear")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_redis()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["GET","POST","PATCH","DELETE"], allow_headers=["Authorization","Content-Type"])
app.include_router(read.router, prefix=settings.api_v1_prefix, tags=["Read"])
app.include_router(auth.router, prefix=settings.api_v1_prefix, tags=["Authentication"])
app.include_router(borrowing.router, prefix=settings.api_v1_prefix, tags=["Borrowing"])
app.include_router(messaging.router, prefix=settings.api_v1_prefix)


def _safe_database_error(exc: MySQLError) -> str:
    """Return a useful connector message with credentials removed."""
    message = str(getattr(exc, "msg", "Database operation failed"))
    # Normalize the connector's account-bearing 1045 message before replacing
    # configured values so neither username nor host-qualified principal leaks.
    message = re.sub(
        r"Access denied for user '[^']+'@'[^']+'",
        "Access denied for configured MySQL account",
        message,
        flags=re.IGNORECASE,
    )
    for secret in (settings.database_password, settings.jwt_secret):
        if secret:
            message = message.replace(secret, "[redacted]")
    if settings.database_user:
        message = message.replace(settings.database_user, "[configured account]")
    return message


@app.get("/health")
def health():
    try:
        with cursor() as (_, cur):
            cur.execute("SELECT COUNT(*) AS items_in_db FROM items")
            result = cur.fetchone()
        return {"status":"ok","items_in_db":result["items_in_db"]}
    except MySQLError as exc:
        logger.warning(
            "Health database check failed (%s, errno=%s, sqlstate=%s) for %s:%s/%s: %s",
            type(exc).__name__, getattr(exc, "errno", "unknown"),
            getattr(exc, "sqlstate", None) or "unknown",
            settings.database_host, settings.database_port, settings.database_name,
            _safe_database_error(exc),
        )
        return JSONResponse(status_code=503,content={"status":"unavailable","detail":"Database unavailable"})


@app.get("/ready")
def readiness():
    mysql_status="ok"
    redis_status="ok"
    try:
        with cursor() as (_,cur):
            cur.execute("SELECT 1")
            cur.fetchone()
    except MySQLError as exc:
        mysql_status="unavailable"
        logger.warning("Readiness MySQL check failed (%s, errno=%s, sqlstate=%s): %s",
                       type(exc).__name__,getattr(exc,"errno","unknown"),
                       getattr(exc,"sqlstate",None) or "unknown",_safe_database_error(exc))
    try:
        check_redis()
    except RedisError as exc:
        redis_status="unavailable"
        logger.warning("Readiness Redis check failed (%s)",type(exc).__name__)
    ready=mysql_status=="ok" and redis_status=="ok"
    return JSONResponse(status_code=200 if ready else 503,
                        content={"status":"ok" if ready else "unavailable",
                                 "mysql":mysql_status,"redis":redis_status})


@app.exception_handler(MySQLError)
async def database_error_handler(_: Request, exc: MySQLError):
    logger.warning("Database request failed (%s): %s", type(exc).__name__, _safe_database_error(exc))
    return JSONResponse(status_code=503,content={"detail":"Database operation unavailable"})
