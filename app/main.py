from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import close_mongo_client
from app.routes.cpus import router as cpus_router
from app.routes.daily_offers import router as daily_offers_router
from app.routes.gpus import router as gpus_router
from app.routes.matches import router as matches_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_mongo_client()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(cpus_router)
app.include_router(gpus_router)
app.include_router(daily_offers_router)
app.include_router(matches_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
