from fastapi import APIRouter

from app.api import cad, health, quotes


api_router = APIRouter()
api_router.include_router(cad.router, prefix="/cad", tags=["cad"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
