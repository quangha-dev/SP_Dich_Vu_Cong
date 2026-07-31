"""Local-only backend entrypoint for running the UI without Docker services."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fakeredis.aioredis import FakeRedis

REPO_ROOT = Path(__file__).resolve().parents[1]
BE_ROOT = REPO_ROOT / "codebase" / "backend"
if str(BE_ROOT) not in sys.path:
    sys.path.insert(0, str(BE_ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


settings = Settings().model_copy(
    update={
        "environment": "LOCAL",
        "database_url": "postgresql+asyncpg://local:local@127.0.0.1:5432/icivi_local",
        "redis_url": "redis://localhost:6379/0",
        "cors_origin": "http://localhost:5173",
        "session_cookie_secure": False,
    }
)

app = create_app(settings=settings, redis_client=FakeRedis(decode_responses=True))
base_lifespan = app.router.lifespan_context


@asynccontextmanager
async def local_lifespan(application):
    async with base_lifespan(application):
        # Keep local chat usable without PostgreSQL/pgvector. The deterministic
        # 207-procedure snapshot still provides grounded answers and citations.
        application.state.procedure_pipeline.rag_service = None
        yield


app.router.lifespan_context = local_lifespan
