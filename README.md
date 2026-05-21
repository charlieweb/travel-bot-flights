# Travel Bot ✈️

> AI-powered flight search assistant that finds the best travel options across airlines and aggregators

## Overview

Travel Bot is a full-stack travel booking application that combines modern web scraping technology with a beautiful user interface to help users discover flight options quickly and efficiently.

### What We're Building

A production-ready travel search platform that:
- **Searches multiple sources** - Airlines and aggregators simultaneously
- **Displays real-time results** - Live pricing and availability (where supported)
- **Provides direct booking links** - Click through to complete purchases
- **Features a modern UI** - Built with Vue 3, Tailwind CSS, and DaisyUI

## Architecture

```
travel-bot/
├── backend/                    # FastAPI + Python 3.13
│   ├── routers/                # API route handlers
│   ├── concurrency.py          # anyio parallel gather helper
│   ├── services/               # Business logic
│   │   └── scraping/           # Scraping + flight parsing
│   │       ├── service.py      # Search orchestration, regex parsers
│   │       ├── ai_parser.py    # Gemini (google-genai) fallback parser
│   │       ├── carriers.py     # Known-airline allowlist
│   │       └── providers/      # Spider + Playwright
│   ├── schemas/                # Pydantic models
│   └── .env                    # Backend environment variables
├── frontend/                   # Nuxt 4 + Vue 3 + TypeScript
│   ├── app/                    # App directory (Nuxt 4)
│   ├── components/             # Vue components
│   ├── stores/                 # Pinia state management
│   └── .env                    # Frontend environment variables
├── docker-compose.yml          # Multi-container orchestration
```

## Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance Python web framework |
| **Uvicorn** | ASGI server for async handling |
| **Scraping Service** | Provider-agnostic abstraction layer |
| **Spider** | Cloud web scraping service |
| **Playwright** | Local browser automation |
| **Google Gemini** | AI fallback parser for scraped flight pages (`google-genai`) |
| **anyio** | Structured async concurrency (task groups, timeouts) |
| **AirLabs API** | Airport data and flight information |
| **Pydantic** | Data validation and serialization |

### Frontend
| Technology | Purpose |
|------------|---------|
| **Nuxt 4** | Full-stack Vue framework |
| **Vue 3** | Progressive JavaScript framework |
| **TypeScript** | Type-safe JavaScript |
| **Pinia** | State management |
| **Tailwind CSS** | Utility-first CSS framework |
| **DaisyUI** | Tailwind CSS component library |
| **Cally** | Web component calendar |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **Docker Compose** | Multi-container orchestration |

## Services Integration

### Scraping Providers

The application supports multiple scraping providers via a provider-agnostic abstraction layer:

| Provider | Type | Cost | Best For |
|----------|------|------|----------|
| **Spider** | Cloud API | Free credits | Quick start, excellent JS rendering |
| **Playwright** | Local | Free | Full browser control, privacy |

#### Spider Cloud
Cloud-based web scraping service with excellent JavaScript rendering:
- Direct URL scraping
- Free credits on signup (no credit card required)
- Get API key at: https://spider.cloud/dashboard

#### Playwright
Local browser automation:
- Full browser control
- Run via `npx playwright install && npx playwright start`
- No API key required

### AirLabs
AirLabs API provides:
- Worldwide airport database
- IATA code resolution
- Airport search by city/name/code

### Flight parsing (regex + Gemini)

After a provider returns page content, `ScrapingService` parses fares in two stages:

1. **Regex-first** — Playwright row blocks, Google Flights price cards, aggregator offer snippets, and known-carrier matching (`carriers.py` allowlist).
2. **Gemini fallback** — If regex finds no fares but the page has price signals, `AIParser` sends a trimmed excerpt to **Google Gemini** and maps the JSON response to `TravelOption` rows.

Set `GOOGLE_API_KEY` in `backend/.env` to enable AI parsing (optional). Without it, search still works using regex only.

```bash
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite   # optional
```

Key files: `backend/services/scraping/service.py`, `ai_parser.py`, `carriers.py`.

## Quick Start with Docker

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### 1. Clone and Configure

```bash
git clone <repository>
cd travel-bot

# Copy environment templates
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edit backend/.env with your configuration
# SCRAPING_PROVIDER=spider  # or 'playwright'
# SPIDER_API_KEY=your_spider_api_key_here
# GOOGLE_API_KEY=your_google_api_key_here   # optional, Gemini parsing
# AIRLABS_API_KEY=your_airlabs_key_here

# The frontend/.env is pre-configured for Docker with:
# NUXT_PUBLIC_API_BASE=http://localhost:8000
# NUXT_INTERNAL_API_BASE=http://backend:8000
```

### 2. Build and Run

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Nuxt web application |
| Backend API | http://localhost:8000 | FastAPI endpoints |
| API Docs | http://localhost:8000/docs | Swagger/OpenAPI documentation |

### 4. Development Mode

For development with hot-reload:

```bash
# Backend (Terminal 1)
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000

# Frontend (Terminal 2)
cd frontend
pnpm install
pnpm run dev
```

## Docker Architecture

### Container Communication

The application uses a multi-container Docker setup with internal networking:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Network                               │
│  ┌─────────────────────┐  ┌─────────────────────┐                  │
│  │   Frontend (Nuxt)   │  │  Backend (FastAPI)  │                  │
│  │   Port: 3000        │  │  Port: 8000          │                  │
│  │   Service: frontend │──│  Service: backend    │                  │
│  └─────────────────────┘  └─────────────────────┘                  │
│           │                       │                                  │
│           │                       │                                  │
│           └───────────────────────┘                                  │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Browser (Outside Docker)                       │  │
│  │  Airport API → http://localhost:8000/api/airports          │  │
│  │  Search API  → http://localhost:8000/api/search_travel      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### API Call Flow

| Component | Call Origin | URL | Resolves To |
|-----------|-------------|-----|-------------|
| **AirportAutocomplete** | Browser (client-side) | `http://localhost:8000` | Host machine's backend container |
| **Search (SSR)** | Docker (server-side) | `http://backend:8000` | Docker internal DNS to backend |

### Environment Variable Split

The application uses separate `.env` files for each service:

| File | Purpose | Example Variables |
|------|---------|-------------------|
| `backend/.env` | Backend service config | `SCRAPING_PROVIDER`, `SPIDER_API_KEY`, `AIRLABS_API_KEY` |
| `frontend/.env` | Frontend service config | `NUXT_PUBLIC_API_BASE`, `NUXT_INTERNAL_API_BASE` |

### Provider Configuration

#### Using Spider Cloud (Cloud - Recommended)
```bash
# backend/.env
SCRAPING_PROVIDER=spider
SPIDER_API_KEY=your_spider_api_key_here
SPIDER_BASE_URL=https://api.spider.cloud
```

#### Using Playwright (Local)
```bash
# backend/.env
SCRAPING_PROVIDER=playwright
PLAYWRIGHT_CDP_URL=http://localhost:9222
```

## Features

### ✈️ Multi-Source Search
Search across major airlines and flight aggregators simultaneously for comprehensive results.

### 📍 Smart Airport Selection
Typeahead search with intelligent matching:
- Airport codes (JFK, LAX, etc.)
- City names (New York, Los Angeles)
- Airport names (John F. Kennedy International)


### 💰 Real-Time Results
Live pricing and availability data where supported by data sources.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/search_travel` | Search flights (all sources, parallel) |
| `POST` | `/api/search_travel/stream` | SSE stream — results per source as they finish |
| `GET` | `/api/airports` | Search airports |
| `GET` | `/health` | Health check |

## What We're Achieving

### Technical Goals
1. **Modern Architecture** - Microservices-ready with Docker
2. **Type Safety** - Full TypeScript coverage
3. **Performance** - Async Python + Vue 3 SSR capabilities
4. **Developer Experience** - Hot-reload, type checking, linting

### User Experience Goals
1. **Fast Search** - Results in seconds, not minutes
2. **Comprehensive Coverage** - Don't miss deals from any source
3. **Beautiful Interface** - Delightful, responsive design
4. **Direct Booking** - No intermediary, book directly with providers

### Business Goals
1. **Open Source** - Community-driven improvements
2. **Extensible** - Easy to add new airlines/aggregators
3. **Cost Effective** - Minimal API costs, maximum value

## Environment Variables

### Backend `.env` (API Keys)

| Variable | Required | Description |
|----------|----------|-------------|
| `SCRAPING_PROVIDER` | Yes | `spider` or `playwright` |
| `SPIDER_API_KEY` | If using Spider | Spider Cloud API key |
| `GOOGLE_API_KEY` | No | Gemini parsing fallback ([get key](https://aistudio.google.com/apikey)) |
| `GEMINI_MODEL` | No | Model id (default: `gemini-3.1-flash-lite`) |
| `AIRLABS_API_KEY` | No | AirLabs API key (optional) |

### Frontend `.env` (API Configuration)

| Variable | Description |
|----------|-------------|
| `NUXT_PUBLIC_API_BASE` | Client-side API URL (`http://localhost:8000` for local, `http://backend:8000` for Docker SSR) |
| `NUXT_INTERNAL_API_BASE` | Server-side API URL for Nuxt SSR (Docker internal: `http://backend:8000`) |

> **Note**: Two API base URLs are needed because:
> - **Browser** calls `http://localhost:8000` directly (works from host machine)
> - **Nuxt SSR** (inside Docker) calls `http://backend:8000` (Docker internal DNS)

## Commands Reference

### Docker
```bash
docker-compose up --build      # Build and start
docker-compose up -d           # Start in background
docker-compose logs -f         # Follow logs
docker-compose down            # Stop and remove
docker-compose down -v         # Stop and remove volumes
```

### Backend
```bash
cd backend
uv sync                        # Install dependencies
uv run uvicorn main:app --reload --port 8000
uv run pytest                  # Run tests
```

### Frontend
```bash
cd frontend
pnpm install                   # Install dependencies
pnpm run dev                   # Development server
pnpm run build                 # Production build
pnpm run preview               # Preview production build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

---

Built with ❤️ using FastAPI, Nuxt, and Vue 3