# Blinkit Price Intelligence — Fullstack

FastAPI backend + HTML/JS frontend, connected to Neon PostgreSQL.

## Project structure

```
blinkit-intelligence/
├── backend/
│   ├── main.py              # FastAPI app, lifespan, CORS, static serving
│   ├── config.py            # Settings from .env
│   ├── database.py          # SQLAlchemy models + init_db()
│   ├── requirements.txt
│   ├── .env                 # ← your keys & DB URL (already filled in)
│   ├── routers/
│   │   ├── products.py      # /api/products/* — fetch, track, history
│   │   ├── browse.py        # /api/category, /api/search, /api/track-bulk
│   │   └── alerts.py        # /api/alerts, /api/zipcodes
│   └── services/
│       ├── syphoon.py       # Syphoon API calls + response parsers
│       ├── intelligence.py  # DB writes, alert detection, history queries
│       └── scheduler.py     # APScheduler — hourly auto-tracking
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js               # All API calls to backend
```

## Run locally

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000 — frontend is served by FastAPI.

## Deploy to Render

1. Push repo to GitHub
2. New Web Service → connect repo
3. Build command:  `pip install -r backend/requirements.txt`
4. Start command:  `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env var:    `DATABASE_URL` = your Neon connection string

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | /api/health | Health check |
| GET | /api/products/fetch | Live product fetch (no DB write) |
| POST | /api/products/track | Track product + first snapshot |
| POST | /api/products/untrack | Stop tracking |
| GET | /api/products/tracked | List all tracked |
| GET | /api/products/history | Price history for product+zip |
| GET | /api/category | Browse category |
| GET | /api/search | Keyword search (page 1) |
| POST | /api/search/next | Keyword search (subsequent pages) |
| POST | /api/track-bulk | Track multiple products at once |
| GET | /api/alerts | List price alerts |
| GET | /api/zipcodes | List tracked zipcodes |
| POST | /api/zipcodes | Add zipcode |
| DELETE | /api/zipcodes/{zip} | Remove zipcode |

## Scheduler

Products are auto-tracked every 60 minutes against all active zipcodes.
Alerts are auto-generated on:
- Price drop > 1%
- Price increase > 1%
- Stock status change (out of stock / back in stock)
