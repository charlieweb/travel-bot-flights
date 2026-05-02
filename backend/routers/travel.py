from fastapi import APIRouter, HTTPException
from typing import List
from schemas.travel import SearchRequest, TravelOption
from services.scraping import ScrapingService

router = APIRouter(prefix="/api", tags=["travel"])

scraping_service = ScrapingService()


@router.post("/search_travel")
async def search_travel(request: SearchRequest):
    print(f"[Router] Incoming search request: {request.dict()}")
    result = await scraping_service.search_travel_options(
        origin=request.origin,
        destination=request.destination,
        depart_date=request.depart_date,
        return_date=request.return_date,
    )
    if not result:
        raise HTTPException(
            status_code=503,
            detail="Scraping failed: All flight search sources blocked access. This may be due to anti-bot protection on airline and aggregator websites."
        )
    return result
