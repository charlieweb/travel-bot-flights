from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.travel import router as travel_router
from routers.airports import router as airports_router
from middleware.error_handlers import register_exception_handlers

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_exception_handlers(app)
    yield


app = FastAPI(title="Travel Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(travel_router)
app.include_router(airports_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
