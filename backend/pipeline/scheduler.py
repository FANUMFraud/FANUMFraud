import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from pipeline.ingest import run_ingest

log = logging.getLogger(__name__)

INGEST_INTERVAL_MINUTES = int(os.getenv("INGEST_INTERVAL_MINUTES", "15"))
INGEST_JOB_ID = "ingest-rss"

_scheduler: BackgroundScheduler | None = None


def _safe_run_ingest() -> None:
    try:
        run_ingest()
    except Exception:
        log.exception("Scheduled ingest failed")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        log.info("Scheduler already running")
        return _scheduler

    scheduler = BackgroundScheduler(timezone="Europe/Warsaw")
    scheduler.add_job(
        _safe_run_ingest,
        trigger=IntervalTrigger(minutes=INGEST_INTERVAL_MINUTES),
        id=INGEST_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=None,
    )
    scheduler.start()
    _scheduler = scheduler
    log.info("Scheduler started, ingest every %d min", INGEST_INTERVAL_MINUTES)
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
    _scheduler = None
