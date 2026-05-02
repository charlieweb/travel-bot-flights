# Travel Bot

## Overview
Travel booking assistant that collects user preferences (origin, destination, dates) and returns flight options via a provider-agnostic scraping service supporting Spider (cloud) and Playwright (local browser automation).

## Tech Stack
- **Frontend**: Nuxt 4 (Vue 3 + TypeScript + Pinia) + Tailwind CSS 4 + DaisyUI 5
- **Backend**: FastAPI (Python 3.13+)
- **Scraping Providers**:
  - **Spider**: Cloud API (excellent JS rendering, free credits)
  - **Playwright**: Local browser automation
- **Architecture**: Provider-agnostic scraping abstraction layer

## Architecture
```
travel-bot/
├── docker-compose.yml          # Multi-container orchestration
├── frontend/                   # Nuxt 4 app
│   ├── .env                    # Nuxt environment variables
│   ├── .env.example            # Environment template
│   ├── app/
│   │   ├── app.vue             # Root app component
│   │   ├── pages/index.vue     # Main page
│   │   ├── components/
│   │   ├── stores/travel.ts    # Pinia store with fetch logic
│   │   └── assets/css/main.css # Tailwind + DaisyUI imports
│   ├── server/
│   │   └── api/
│   │       └── search_travel.post.ts  # SSR proxy route
│   ├── nuxt.config.ts          # Nuxt configuration
│   └── package.json
├── backend/                    # FastAPI app
│   ├── main.py                 # FastAPI entrypoint with lifespan
│   ├── routers/
│   │   ├── travel.py           # POST /api/search_travel
│   │   └── airports.py         # GET /api/airports
│   ├── schemas/                # Pydantic models
│   ├── services/               # Business logic services
│   │   ├── scraping/           # Provider-agnostic scraping layer
│   │   │   ├── __init__.py     # Service exports (ScrapingService)
│   │   │   ├── service.py      # Main facade with business logic
│   │   │   └── providers/      # Provider implementations
│   │   │       ├── __init__.py # Factory (get_provider)
│   │   │       ├── base.py     # Abstract ScrapingProvider
│   │   │       ├── spider.py   # Spider Cloud provider
│   │   │       └── playwright_provider.py  # Playwright provider
│   │   ├── airlabs_service.py  # AirLabs integration
│   │   └── mock_airports.py    # Fallback mock data
│   ├── pyproject.toml
│   ├── .env                    # Backend environment variables
│   ├── .env.example            # Backend env template
│   └── .venv/
```

## Commands

### Docker (Production)
```bash
# Start all services
docker-compose up --build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Backend (Development)
```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

### Frontend (Development)
```bash
cd frontend
pnpm install
pnpm run dev # http://localhost:3000
```

## Docker Compose Structure

### Services

| Service | Image | Port | Purpose | Environment |
|---------|-------|------|---------|-------------|
| `backend` | FastAPI + Uvicorn | `8000:8000` | Main API | `SCRAPING_PROVIDER`, `SPIDER_API_KEY`, `AIRLABS_API_KEY` |
| `frontend` | Nuxt SSR | `3000:3000` | Web UI | `NUXT_PUBLIC_API_BASE`, `NUXT_INTERNAL_API_BASE`, `PORT` |

### Network Configuration

- **Network**: `travel-bot-network` (bridge driver)
- **Service Dependencies**:
  - Frontend waits for backend to be healthy
- **Health Checks**:
  - Backend: `curl -f http://localhost:8000/health`
  - Frontend: HTTP GET on `http://localhost:3000`

### Environment Variable Split

The frontend uses two different API base URLs:

1. **`NUXT_PUBLIC_API_BASE=http://localhost:8000`**
   - Used by: `AirportAutocomplete.vue` (client-side browser fetch)
   - Resolves to: Host machine's localhost (backend container exposed port)

2. **`NUXT_INTERNAL_API_BASE=http://backend:8000`**
   - Used by: `search_travel.post.ts` (Nuxt SSR proxy route)
   - Resolves to: Docker internal DNS (`backend` service name)

This split is required because:
- **Browser** (outside Docker) → calls `localhost:8000` → reaches backend via port mapping
- **Nuxt SSR** (inside Docker) → calls `backend:8000` → reaches backend via Docker DNS

### Environment Files

| File | Purpose | Variables |
|------|---------|-----------|
| `backend/.env` | Backend service config | `SCRAPING_PROVIDER`, `SPIDER_API_KEY`, `AIRLABS_API_KEY` |
| `frontend/.env` | Frontend service config | `NUXT_PUBLIC_API_BASE`, `NUXT_INTERNAL_API_BASE` |

### Frontend
- Use `pnpm` for package management
- Nuxt 4 uses `app/` directory structure
- Tailwind CSS 4 with `@tailwindcss/vite` plugin
- DaisyUI 5 for UI components (imported in main.css)
- Pinia with `@pinia/nuxt`
- API calls via `$fetch` from Pinia store
- **SSR Proxy**: Search calls go through `server/api/search_travel.post.ts` for CORS handling

### Backend
- FastAPI with lifespan context manager for startup/shutdown
- Routers pattern: `routers/` directory
- Schemas pattern: `schemas/` directory with Pydantic models
- **Scraping Service**: Provider-agnostic abstraction in `services/scraping/`
  - `ScrapingService` facade: business logic for flight search
  - `ScrapingProvider` base class: unified interface for all providers
  - **Supported Providers**:
    - `SpiderCloudProvider`: Cloud API (excellent JS rendering, free credits)
    - `PlaywrightProvider`: Local browser automation
  - Provider selection via `SCRAPING_PROVIDER` env var
  - Falls back to mock data if provider fails or no API key configured
- **AirLabs Service**: Airport data lookup with mock fallback
- Backend CORS allows `http://localhost:3000` (Nuxt frontend)
- Environment: `backend/.env` for all service configuration

### Docker Integration
- **Backend `.env`**: Service-specific config (`SCRAPING_PROVIDER`, `SPIDER_API_KEY`, `AIRLABS_API_KEY`)
- **Frontend `.env`**: Nuxt-specific config (`NUXT_PUBLIC_API_BASE`, `NUXT_INTERNAL_API_BASE`)
- **docker-compose.yml**: Uses `env_file` directive to load service-specific `.env` files
- **Port Mapping**: Frontend `3000:3000`, Backend `8000:8000`
- **Internal Networking**: Services communicate via Docker bridge network `travel-bot-network`

## Provider Configuration

### Spider Cloud (Cloud - Recommended)
```bash
# backend/.env
SCRAPING_PROVIDER=spider
SPIDER_API_KEY=your_spider_api_key_here
SPIDER_BASE_URL=https://api.spider.cloud
```
Get your API key at: https://spider.cloud/dashboard (free credits on signup)

### Playwright (Local Browser)
```bash
# backend/.env
SCRAPING_PROVIDER=playwright
PLAYWRIGHT_CDP_URL=http://localhost:9222
```
Run: `npx playwright install && npx playwright start`

### Switching Providers
Simply change `SCRAPING_PROVIDER` in `backend/.env` and restart:
```bash
docker-compose down && docker-compose up -d
```