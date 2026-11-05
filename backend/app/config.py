import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_cors_origins() -> list[str]:
    configured = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
    local_frontends = {"http://localhost:3000", "http://127.0.0.1:3000"}
    if local_frontends.intersection(configured):
        configured.extend(origin for origin in local_frontends if origin not in configured)
    return configured


class Settings:
    app_name: str = os.getenv("APP_NAME", "BorrowNear API")
    app_env: str = os.getenv("APP_ENV", "development")
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    database_host: str = os.getenv("DATABASE_HOST", "localhost")
    database_port: int = int(os.getenv("DATABASE_PORT", "3306"))
    database_name: str = os.getenv("DATABASE_NAME", "borrownear")
    database_user: str = os.getenv("DATABASE_USER", "borrownear_app")
    database_password: str = os.getenv("DATABASE_PASSWORD", "")
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    cors_origins: list[str] = _get_cors_origins()
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "60"))
    item_image_dir: str = os.getenv("ITEM_IMAGE_DIR", str(Path(__file__).resolve().parents[1] / "data" / "item_images"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
