import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ExternalAPIException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=detail)


class InternalServerException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)


class APIKeyNotConfiguredException(HTTPException):
    def __init__(self):
        super().__init__(status_code=500, detail="External API key not configured")


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {str(exc)}"},
    )


async def httpx_exception_handler(request: Request, exc: httpx.HTTPError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": f"Error fetching data from external API: {str(exc)}"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ExternalAPIException, http_error_handler)
    app.add_exception_handler(InternalServerException, http_error_handler)
    app.add_exception_handler(APIKeyNotConfiguredException, http_error_handler)
    app.add_exception_handler(httpx.HTTPError, httpx_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)