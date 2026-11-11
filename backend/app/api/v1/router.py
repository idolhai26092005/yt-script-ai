from fastapi import APIRouter
from app.api.v1.endpoints.gemini import router as gemini_router
from app.api.v1.endpoints.transcript import router as transcript_router
from app.api.v1.endpoints.admin_keys import router as admin_keys_router
from app.api.v1.endpoints.topics import router as topics_router
from app.api.v1.endpoints.script_production import router as production_router
from app.api.v1.endpoints.history import router as history_router
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(gemini_router, prefix="/gemini", tags=["gemini"])
api_router.include_router(transcript_router, prefix="/transcript", tags=["transcript"])
api_router.include_router(admin_keys_router, prefix="/admin/keys", tags=["admin-keys"])
api_router.include_router(topics_router, prefix="/topics", tags=["topics"])
api_router.include_router(production_router, prefix="/production", tags=["production"])

# Unified history guard: archive reads stay mounted regardless of generation
# feature flags so saved single-project history never disappears.
api_router.include_router(history_router, prefix="/history", tags=["history"])

# Series isolation guard: keep series unmounted by default; when enabled, mount
# the rebuilt v2 implementation on the stable `/series` path.
if settings.ENABLE_SERIES_FLOW:
    from app.api.v1.endpoints.series import router as series_router

    api_router.include_router(series_router, prefix="/series", tags=["series"])
