from fastapi import APIRouter

router = APIRouter()


def make_health_router(service_name: str) -> APIRouter:
    """
    Returns an APIRouter with a GET /health endpoint for the given service.
    No authentication required. Mount this before protected routes.
    """
    health_router = APIRouter()

    @health_router.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok", "service": service_name}

    return health_router
