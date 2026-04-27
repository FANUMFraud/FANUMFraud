import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

from pipeline.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="FANUMFraud", lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok", "message": "FANUMFraud działa"}
