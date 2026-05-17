from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from services.logger import configure_logging, log

configure_logging()

try:
    from prometheus_fastapi_instrumentator import Instrumentator as _Instrumentator
    _INSTRUMENTATOR_AVAILABLE = True
except ImportError:  # pragma: no cover - package may be absent in local sandbox
    _INSTRUMENTATOR_AVAILABLE = False

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.v2 import auth as v2_auth
from routers.v2 import documents as v2_documents
from routers.v2 import admin as v2_admin
from routers.v2 import hydrants as v2_hydrants
from routers.v2 import fire_stations as v2_fire_stations
from routers.v2 import buildings as v2_buildings
from routers.v2 import inspector as v2_inspector
from routers.v2 import cities as v2_cities
from routers.v2 import kpi as v2_kpi
from routers.v2 import risk_map as v2_risk_map
from routers.v2 import operations as v2_operations
from routers.v2 import forecast as v2_forecast
from routers.v2 import recommendations as v2_recommendations
from routers.v2 import chat as v2_chat
from routers.v2 import telegram as v2_telegram
from routers.v2 import inspection_plan as v2_inspection_plan
from routers.v2 import routing as v2_routing
from middleware.audit import AuditMiddleware
from services.telegram_service import telegram_service

scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if telegram_service.is_configured() and not scheduler.running:
        scheduler.add_job(
            telegram_service.send_test_alert,
            CronTrigger(hour=8, minute=0, timezone="UTC"),
            args=["astana", []],
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
app.add_middleware(AuditMiddleware)

if _INSTRUMENTATOR_AVAILABLE:
    _Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# --- API v2 ---
app.include_router(v2_auth.router, prefix="/api/v2/auth", tags=["auth-v2"])
app.include_router(v2_documents.router, prefix="/api/v2/documents", tags=["documents-v2"])
app.include_router(v2_admin.router, prefix="/api/v2/admin", tags=["admin-v2"])
app.include_router(v2_hydrants.router, prefix="/api/v2", tags=["hydrants-v2"])
app.include_router(v2_fire_stations.router, prefix="/api/v2", tags=["stations-v2"])
app.include_router(v2_buildings.router, prefix="/api/v2", tags=["buildings-v2"])
app.include_router(v2_inspector.router, prefix="/api/v2", tags=["inspector-v2"])
app.include_router(v2_cities.router, prefix="/api/v2", tags=["cities-v2"])
app.include_router(v2_kpi.router, prefix="/api/v2", tags=["kpi-v2"])
app.include_router(v2_risk_map.router, prefix="/api/v2", tags=["risk-map-v2"])
app.include_router(v2_operations.router, prefix="/api/v2", tags=["operations-v2"])
app.include_router(v2_forecast.router, prefix="/api/v2", tags=["forecast-v2"])
app.include_router(v2_recommendations.router, prefix="/api/v2", tags=["recommendations-v2"])
app.include_router(v2_chat.router, prefix="/api/v2", tags=["chat-v2"])
app.include_router(v2_telegram.router, prefix="/api/v2", tags=["telegram-v2"])
app.include_router(v2_inspection_plan.router, prefix="/api/v2", tags=["inspection-plan-v2"])
app.include_router(v2_routing.router, prefix="/api/v2", tags=["routing-v2"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
