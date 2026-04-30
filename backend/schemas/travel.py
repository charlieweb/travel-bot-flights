from pydantic import BaseModel
from datetime import date


class SearchRequest(BaseModel):
    origin: str
    destination: str
    depart_date: date
    return_date: date


class TravelOption(BaseModel):
    id: int
    airline: str
    price: float
    depart_time: str
    arrival_time: str
    duration: str
    stops: int
    source_url: str | None = None
    source_type: str = "airline"
    depart_date: str | None = None
    return_date: str | None = None
