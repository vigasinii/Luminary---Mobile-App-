from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import os

from config import settings
from database import init_db
from services.scheduler import start_scheduler, stop_scheduler
from routers import products, browse, alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising DB...")
    await init_db()
    logger.info("DB ready. Starting scheduler...")
    start_scheduler(interval_minutes=60)
    yield
    logger.info("Shutting down...")
    stop_scheduler()


app = FastAPI(
    title="Blinkit Price Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(products.router, prefix="/api")
app.include_router(browse.router,   prefix="/api")
app.include_router(alerts.router,   prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
