from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import (
    auth,
    buildings,
    chat,
    cities,
    forecast,
    hydrants,
    incidents,
    inspection_plan,
    inspector,
    kpi,
    operations,
    recommendations,
    stations,
    telegram,
)
from services.telegram_service import telegram_service
from services.db import database_service

API_PREFIX = "/api/v1"
scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(_: FastAPI):
    database_service.apply_migrations()
    database_service.seed_buildings()
    database_service.seed_incidents()
    database_service.seed_operations()
    if telegram_service.is_configured() and not scheduler.running:
        scheduler.add_job(
            telegram_service.send_test_alert,
            CronTrigger(hour=8, minute=0, timezone="UTC"),
            args=["astana"],
            id="daily_telegram_digest",
            replace_existing=True,
        )
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)

app = FastAPI(title="FireWatch API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cities.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(buildings.router, prefix=API_PREFIX)
app.include_router(incidents.router, prefix=API_PREFIX)
app.include_router(forecast.router, prefix=API_PREFIX)
app.include_router(recommendations.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(kpi.router, prefix=API_PREFIX)
app.include_router(inspector.router, prefix=API_PREFIX)
app.include_router(inspection_plan.router, prefix=API_PREFIX)
app.include_router(operations.router, prefix=API_PREFIX)
app.include_router(stations.router, prefix=API_PREFIX)
app.include_router(hydrants.router, prefix=API_PREFIX)
app.include_router(telegram.router, prefix=API_PREFIX)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
