from typing import Annotated
from fastapi import APIRouter, Depends, Query
from services.airlabs_service import AirLabsService, get_airlabs_service
from schemas.airport import Airport

router = APIRouter(prefix="/api", tags=["airports"])


@router.get("/airports", response_model=list[Airport])
async def search_airports(
    service: Annotated[AirLabsService, Depends(get_airlabs_service)],
    query: str = Query(..., min_length=1, description="Search query for airports"),
) -> list[Airport]:
    """Search airports by code, name, or city using AirLabs API"""
    return await service.search_airports(query=query)


@router.get("/airports/all", response_model=list[Airport])
async def get_all_airports(
    service: Annotated[AirLabsService, Depends(get_airlabs_service)],
) -> list[Airport]:
    """Get all airports from AirLabs API"""
    return await service.get_all_airports()
