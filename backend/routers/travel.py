import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from schemas.travel import SearchRequest, TravelOption
from services.scraping import ScrapingService

router = APIRouter(prefix="/api", tags=["travel"])

scraping_service = ScrapingService()


def _request_dates(request: SearchRequest) -> tuple[str, str | None]:
    depart = request.depart_date.isoformat()
    ret = request.return_date.isoformat() if request.return_date else None
    return depart, ret


@router.post("/search_travel", response_model=list[TravelOption])
async def search_travel(request: SearchRequest):
    print(f"[Router] Incoming search request: {request.model_dump()}")
    depart_date, return_date = _request_dates(request)

    try:
        result = await scraping_service.search_travel_options(
            origin=request.origin,
            destination=request.destination,
            depart_date=depart_date,
            return_date=return_date,
        )
    except Exception as exc:
        print(f"[Router] Search failed: {exc}")
        result = []

    if not result:
        result = scraping_service._make_search_fallbacks(
            request.origin,
            request.destination,
            depart_date,
            return_date,
            reason="no_results",
        )

    if not result:
        status = scraping_service.source_status
        detail = _build_empty_detail(status)
        raise HTTPException(status_code=503, detail=detail)

    return result


@router.post("/search_travel/stream")
async def search_travel_stream(request: SearchRequest):
    """SSE stream: quick booking links first, then fares as each source finishes."""
    depart_date, return_date = _request_dates(request)

    async def event_stream():
        try:
            async for event in scraping_service.search_travel_stream(
                origin=request.origin,
                destination=request.destination,
                depart_date=depart_date,
                return_date=return_date,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            print(f"[Router] Stream error: {exc}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc), 'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_empty_detail(status: dict[str, str]) -> str:
    blocked = [s for s, v in status.items() if v.startswith("blocked")]
    failed = [s for s, v in status.items() if v.startswith("error")]
    no_data = [s for s, v in status.items() if v.startswith("no_data")]

    detail_parts = []
    if blocked:
        detail_parts.append(f"{len(blocked)} sources blocked")
    if no_data:
        detail_parts.append(f"{len(no_data)} sources returned no flight data")
    if failed:
        detail_parts.append(f"{len(failed)} sources errored")

    detail = ". ".join(detail_parts) if detail_parts else "All flight search sources returned no results"
    return detail + ". Try searching on Google Flights directly."
