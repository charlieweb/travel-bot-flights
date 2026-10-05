import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.travel import router as travel_router
from routers.airports import router as airports_router
from routers.search import router as search_router
from middleware.error_handlers import register_exception_handlers

load_dotenv()

_DEFAULT_ORIGINS = (
    "http://localhost:3000,"
    "https://frontend-production-6d6e.up.railway.app"
)
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_exception_handlers(app)
    yield


app = FastAPI(title="Travel Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(travel_router)
app.include_router(airports_router)
app.include_router(search_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
