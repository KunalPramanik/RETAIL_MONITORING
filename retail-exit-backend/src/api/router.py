"""API Route Aggregator Module"""

from fastapi import APIRouter, Depends
from src.api.deps import get_current_user

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
from src.api.forensics_routes import router as forensics_router
from src.api.smart_wall_routes import router as smart_wall_router
from src.api.evidence_routes import router as evidence_router
from src.api.health_routes import router as health_router
from src.api.integration_routes import router as integration_router
from src.api.inventory_routes import router as inventory_router
from src.api.dispatch import router as dispatch_router
from src.api.materials import router as materials_router
from src.api.material_flow import router as material_flow_router
from src.api.tripwire import router as tripwire_router
from src.api.analytics_routes import router as analytics_router
from src.api.advanced_routes import router as advanced_router
from src.api.auth import router as auth_router
from src.api.platform_routes import router as platform_router

api_router = APIRouter(prefix="/api")

auth_dep = [Depends(get_current_user)]

# Data routes with mandatory JWT authentication
api_router.include_router(kpis_router, dependencies=auth_dep)
api_router.include_router(events_router, dependencies=auth_dep)
api_router.include_router(alerts_router, dependencies=auth_dep)
api_router.include_router(products_router, dependencies=auth_dep)
api_router.include_router(material_flow_router, dependencies=auth_dep)
api_router.include_router(materials_router, dependencies=auth_dep)
api_router.include_router(employees_router, dependencies=auth_dep)
api_router.include_router(invoices_router, dependencies=auth_dep)
api_router.include_router(reports_router, dependencies=auth_dep)
api_router.include_router(settings_router, dependencies=auth_dep)
api_router.include_router(lanes_router, dependencies=auth_dep)
api_router.include_router(ingest_router, dependencies=auth_dep)
api_router.include_router(cameras_router, dependencies=auth_dep)
api_router.include_router(hardware_router, dependencies=auth_dep)
api_router.include_router(discovery_router, dependencies=auth_dep)
api_router.include_router(model_router, dependencies=auth_dep)
api_router.include_router(forensics_router, dependencies=auth_dep)
api_router.include_router(smart_wall_router, dependencies=auth_dep)
api_router.include_router(evidence_router, dependencies=auth_dep)
api_router.include_router(integration_router, dependencies=auth_dep)
api_router.include_router(inventory_router, dependencies=auth_dep)
api_router.include_router(dispatch_router, dependencies=auth_dep)
api_router.include_router(tripwire_router, dependencies=auth_dep)
api_router.include_router(analytics_router, dependencies=auth_dep)
api_router.include_router(advanced_router, dependencies=auth_dep)

# Allow-listed routers with public entrypoints
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(platform_router)

