from typing import Annotated

from fastapi import APIRouter, Depends

from schemas.search import ParseSearchRequest, ParsedSearch
from services.airport_service import AirportService, get_airport_service
from services.llm_client import LLMClient, get_llm_client
from services.search_parser import SearchParser

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/parse_search", response_model=ParsedSearch)
async def parse_search(
    body: ParseSearchRequest,
    llm: Annotated[LLMClient, Depends(get_llm_client)],
    airports: Annotated[AirportService, Depends(get_airport_service)],
) -> ParsedSearch:
    """Parse a natural-language flight search into origin/destination/dates."""
    parser = SearchParser(llm=llm, airports=airports)
    return await parser.parse(body.query)
