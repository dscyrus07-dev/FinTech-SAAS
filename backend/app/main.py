import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import upload as upload
from app.routers import download
from app.api.routes import upload as hdfc_upload
from app.api.routes import sync as sync_api

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(upload.router, tags=["Processing"])
app.include_router(download.router, tags=["Download"])
app.include_router(hdfc_upload.router, prefix="/api", tags=["HDFC Processing"])
app.include_router(sync_api.router, prefix="/api", tags=["Sync"])


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "airco-insights", "version": settings.VERSION}

