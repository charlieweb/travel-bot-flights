from fastapi import APIRouter
from typing import List
from schemas.travel import SearchRequest, TravelOption
from services.scraping import ScrapingService

router = APIRouter(prefix="/api", tags=["travel"])

# Initialize scraping service with configured provider
scraping_service = ScrapingService()


@router.post("/search_travel", response_model=List[TravelOption])
async def search_travel(request: SearchRequest) -> List[TravelOption]:
    result = await scraping_service.search_travel_options(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        return_date=request.return_date,
    )
    return result
