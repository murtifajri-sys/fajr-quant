"""FastAPI entrypoint aggregating all routers."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    bandarmology,
    charts,
    data,
    recommendations,
    scoring,
    screener,
    stocks,
    tasks,
    technical,
    telegram,
    tokens,
    watchlist,
)
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Stock analysis platform (technical + bandarmology + AI scoring).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.APP_NAME}


prefix = settings.API_PREFIX
app.include_router(tokens.router, prefix=prefix)
app.include_router(telegram.router, prefix=prefix)
app.include_router(stocks.router, prefix=prefix)
app.include_router(technical.router, prefix=prefix)
app.include_router(bandarmology.router, prefix=prefix)
app.include_router(scoring.router, prefix=prefix)
app.include_router(screener.router, prefix=prefix)
app.include_router(charts.router, prefix=prefix)
app.include_router(recommendations.router, prefix=prefix)
app.include_router(tasks.router, prefix=prefix)
app.include_router(data.router, prefix=prefix)
app.include_router(watchlist.router, prefix=prefix)
