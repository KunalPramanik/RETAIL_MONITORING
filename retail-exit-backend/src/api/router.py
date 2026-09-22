"""API Route Aggregator Module"""

from fastapi import APIRouter

from src.api.kpis import router as kpis_router
from src.api.events import router as events_router
from src.api.alerts import router as alerts_router
from src.api.products import router as products_router
from src.api.employees import router as employees_router
from src.api.invoices import router as invoices_router
from src.api.reports import router as reports_router
from src.api.settings import router as settings_router
from src.api.lanes import router as lanes_router
from src.api.ingest import router as ingest_router
from src.api.cameras import router as cameras_router
from src.api.hardware import router as hardware_router
from src.api.discovery import router as discovery_router
from src.api.model_routes import router as model_router
from src.api.dispatch import router as dispatch_router
from src.api.materials import router as materials_router
from src.api.tripwire import router as tripwire_router
from src.api.analytics_routes import router as analytics_router

api_router = APIRouter(prefix="/api")

api_router.include_router(kpis_router)
api_router.include_router(events_router)
api_router.include_router(alerts_router)
api_router.include_router(products_router)
api_router.include_router(materials_router)
api_router.include_router(employees_router)
api_router.include_router(invoices_router)
api_router.include_router(reports_router)
api_router.include_router(settings_router)
api_router.include_router(lanes_router)
api_router.include_router(ingest_router)
api_router.include_router(cameras_router)
api_router.include_router(hardware_router)
api_router.include_router(discovery_router)
api_router.include_router(model_router)
api_router.include_router(dispatch_router)
api_router.include_router(tripwire_router)
api_router.include_router(analytics_router)

