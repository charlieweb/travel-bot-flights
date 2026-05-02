# Backend

FastAPI travel bot API with Spider Cloud and Playwright scraping providers.

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

### Scraping Provider
```bash
SCRAPING_PROVIDER=spider  # Options: spider, playwright
```

### Spider Cloud (Cloud - Recommended)
```bash
SPIDER_API_KEY=your_spider_api_key_here
SPIDER_BASE_URL=https://api.spider.cloud
```
Get your free API key at: https://spider.cloud/dashboard

### Playwright (Local Browser)
```bash
SCRAPING_PROVIDER=playwright
PLAYWRIGHT_CDP_URL=http://localhost:9222
```
Run `npx playwright install && npx playwright start` before using.

### AirLabs (Optional)
```bash
AIRLABS_API_KEY=your_airlabs_api_key_here
```
Used for airport data lookups. Get your API key at: https://airlabs.co