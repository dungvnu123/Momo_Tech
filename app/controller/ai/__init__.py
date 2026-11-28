from fastapi import APIRouter

from .entities import router as entity_router
from .shield import router as shield_router
from .transfer import router as transfer_router
from .triage import router as triage_router
from .pipeline import router as pipeline_router
from .realtime import router as realtime_router

router = APIRouter(prefix="/api/ai")
for feature_router in (shield_router, entity_router, triage_router, transfer_router, pipeline_router, realtime_router):
    router.include_router(feature_router)
