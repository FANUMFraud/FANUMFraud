import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup / shutdown hooks
    # Startup
    logger.info("Initialising database tables...")
    init_db()

    try:
        from elastic import init_index

        init_index()
    except Exception:
        logger.warning("Elasticsearch unavailable at startup -- search will use SQL fallback")

    yield
    # Shutdown

    logger.info("Shutting down.")


app = FastAPI(
    title="FanumFraud",
    description="Company reputation monitoring system - AML risk scoring",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow the frontend on any port during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers

from routes.companies import router as companies_router  # noqa: E402
from routes.articles import router as articles_router  # noqa: E402

app.include_router(companies_router)
app.include_router(articles_router)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "FanumFraud"}
