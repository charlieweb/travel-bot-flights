from pydantic import BaseModel


class Airport(BaseModel):
    code: str
    name: str
    city: str
    country: str


class AirportSearchResponse(BaseModel):
    airports: list[Airport]
    total: int