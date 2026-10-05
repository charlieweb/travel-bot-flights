from typing import Annotated
from fastapi import APIRouter, Depends, Query
from services.airport_service import AirportService, get_airport_service
from schemas.airport import Airport

router = APIRouter(prefix="/api", tags=["airports"])


@router.get("/airports", response_model=list[Airport])
async def search_airports(
    service: Annotated[AirportService, Depends(get_airport_service)],
    query: str = Query(..., min_length=1, description="Search query for airports"),
) -> list[Airport]:
    """Search airports by code, name, or city from local airports.json"""
    return service.search_airports(query=query)


@router.get("/airports/all", response_model=list[Airport])
async def get_all_airports(
    service: Annotated[AirportService, Depends(get_airport_service)],
) -> list[Airport]:
    """Get airports from local airports.json"""
    return service.get_all_airports()
