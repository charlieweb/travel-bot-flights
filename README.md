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
├── backend/          # FastAPI + Python 3.12
│   ├── routers/      # API route handlers
│   ├── services/     # Business logic (Firecrawl, AirLabs)
│   └── schemas/      # Pydantic models
└── frontend/         # Nuxt 4 + Vue 3 + TypeScript
    ├── app/          # App directory (Nuxt 4)
    ├── components/   # Vue components
    └── stores/       # Pinia state management
```

## Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | High-performance Python web framework |
| **Uvicorn** | ASGI server for async handling |
| **Firecrawl** | Web scraping service for flight data |
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

### Firecrawl
We use [Firecrawl](https://firecrawl.dev) to scrape flight data from:
- **7 Airlines**: Delta, United, American, Southwest, Avianca, Copa, Aeromexico
- **4 Aggregators**: Google Flights, Kayak, Skyscanner, Expedia

### AirLabs
AirLabs API provides:
- Worldwide airport database
- IATA code resolution
- Airport search by city/name/code

## Quick Start with Docker

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### 1. Clone and Configure

```bash
git clone <repository>
cd travel-bot

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
# FIRECRAWL_API_KEY=your_key_here
# AIRLABS_API_KEY=your_key_here
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

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

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
| `POST` | `/api/search-travel` | Search flights |
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

| Variable | Required | Description |
|----------|----------|-------------|
| `FIRECRAWL_API_KEY` | Yes | Firecrawl API key |
| `AIRLABS_API_KEY` | No | AirLabs API key (optional) |

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
