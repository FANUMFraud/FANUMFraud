import logging
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, check_database_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FanumFraud",
    description="System monitorowania reputacji firm",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    """Inicjalizacja aplikacji przy starcie."""
    logger.info("🚀 Startup FanumFraud")
    init_db()


@app.get("/")
async def root() -> Dict[str, str]:
    """
    Główny endpoint - sprawdzenie czy aplikacja działa.

    Returns:
        Dict z statusem aplikacji
    """
    return {
        "status": "ok",
        "message": "FanumFraud działa!",
    }


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint - sprawdzenie połączenia z bazą danych.

    Returns:
        Dict z statusem bazy danych
    """
    if check_database_connection():
        return {"database": "ok"}
    else:
        return {"database": "error"}