"""
Background folder import tasks: job store and sync runner for async folder scanning.
Runs the actual scan in a thread pool so the API worker is not blocked.
"""
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging_config import get_logger
from app.db.session import SessionLocal
from app.services.import_service import import_folder

logger = get_logger(__name__)

# Thread pool for running sync folder imports (max 2 concurrent scans)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="import_folder")


@dataclass
class ImportJobStatus:
    """Status of a folder import job."""

    job_id: str
    folder_path: str
    status: str  # pending | running | completed | failed
    created_at: datetime
    updated_at: datetime | None = None
    result: dict[str, Any] | None = None  # imported_count, folder_id, songs | error

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "folder_path": self.folder_path,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "result": self.result,
        }


# In-memory job store (single process). For multi-worker deployments use Redis/DB.
# Capped at 500 jobs; oldest evicted when full.
_MAX_JOBS = 500
_import_jobs: dict[str, ImportJobStatus] = {}


def create_folder_import_job(folder_path: str) -> str:
    """Create a new pending job and return job_id."""
    while len(_import_jobs) >= _MAX_JOBS:
        oldest = min(_import_jobs.items(), key=lambda x: x[1].created_at)
        del _import_jobs[oldest[0]]
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    _import_jobs[job_id] = ImportJobStatus(
        job_id=job_id,
        folder_path=folder_path,
        status="pending",
        created_at=now,
        updated_at=None,
        result=None,
    )
    return job_id


def get_import_job(job_id: str) -> ImportJobStatus | None:
    """Return job status if it exists."""
    return _import_jobs.get(job_id)


def list_import_jobs(limit: int = 50) -> list[ImportJobStatus]:
    """Return most recent jobs (newest first)."""
    jobs = sorted(_import_jobs.values(), key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]


def _run_folder_import_sync(job_id: str, folder_path: str) -> None:
    """
    Run folder import in a background thread. Uses its own DB session.
    Updates job status to running, then completed or failed.
    """
    job = _import_jobs.get(job_id)
    if not job or job.status != "pending":
        return
    now = datetime.now(timezone.utc)
    job.status = "running"
    job.updated_at = now

    db = SessionLocal()
    try:
        logger.info("Background folder import started", extra={"job_id": job_id, "folder_path": folder_path})
        imported, folder = import_folder(db, folder_path, create_folder_record=True)
        db.commit()
        for s in imported:
            db.refresh(s)
        if folder:
            db.refresh(folder)
        job.status = "completed"
        job.updated_at = datetime.now(timezone.utc)
        job.result = {
            "imported_count": len(imported),
            "folder_id": folder.id if folder else None,
            "song_ids": [s.id for s in imported],
        }
        logger.info(
            "Background folder import completed",
            extra={"job_id": job_id, "imported_count": len(imported), "folder_id": folder.id if folder else None},
        )
    except Exception as e:
        logger.exception("Background folder import failed", extra={"job_id": job_id, "folder_path": folder_path})
        job.status = "failed"
        job.updated_at = datetime.now(timezone.utc)
        job.result = {"error": str(e)}
    finally:
        db.close()


def schedule_folder_import(job_id: str, folder_path: str) -> None:
    """
    Schedule folder import to run in a background thread (fire-and-forget).
    Call from an async route so the event loop is available; returns immediately.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_folder_import_sync, job_id, folder_path)
