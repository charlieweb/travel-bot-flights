from typing import Optional

from pydantic import BaseModel, Field


class ParseSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class ParsedSearch(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    depart_date: Optional[str] = None
    return_date: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
