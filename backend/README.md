# Backend

FastAPI travel bot API with Firecrawl integration.

## Setup

```bash
uv sync
```

## Run

### Using uv (recommended)
```bash
uv run uvicorn main:app --reload --port 8000
```

### Using Python directly (local development)
```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate     # Windows

# Run with uvicorn
uvicorn main:app --reload --port 8000

# Or run with Python
python -m uvicorn main:app --reload --port 8000
```

## API Docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Test API

```bash
curl -X POST http://localhost:8000/api/search_travel \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "NYC",
    "destination": "LAX",
    "depart_date": "2026-05-01",
    "return_date": "2026-05-10"
  }'
```

## Environment

Set these variables in `.env` file:

- `FIRECRAWL_API_KEY` - Firecrawl API key for travel search
- `AIRLABS_API_KEY` - AirLabs API key for airport data
