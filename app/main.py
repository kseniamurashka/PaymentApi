from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, session_factory
from app.routes import router
from app.seed import seed_tariffs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        with session_factory() as session:
            seed_tariffs(session)
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Kvitto Payments API",
    lifespan=lifespan,
)

app.include_router(router)
