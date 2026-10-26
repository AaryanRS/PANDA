import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.routes.health import router as health_router
from app.routes.issues import router as issues_router
from app.routes.repository import router as repository_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="PANDA API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(repository_router, prefix="/api")
app.include_router(issues_router, prefix="/api")
