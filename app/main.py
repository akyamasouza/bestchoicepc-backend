from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import register_error_handlers
from app.core.config import settings
from app.core.database import close_mongo_client
from app.routes.cpus import router as cpus_router
from app.routes.daily_offers import router as daily_offers_router
from app.routes.gpus import router as gpus_router
from app.routes.matches import router as matches_router
from app.routes.motherboards import router as motherboards_router
from app.routes.psus import router as psus_router
from app.routes.rams import router as rams_router
from app.routes.ssds import router as ssds_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_mongo_client()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cpus_router)
app.include_router(gpus_router)
app.include_router(ssds_router)
app.include_router(rams_router)
app.include_router(motherboards_router)
app.include_router(psus_router)
app.include_router(daily_offers_router)
app.include_router(matches_router)
