"""
Background folder import tasks: job store and sync runner for async folder scanning.
Runs the actual scan in a thread pool so the API worker is not blocked.
Now uses persistent ImportJob DB model instead of in-memory dict.
"""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logging_config import get_logger
from app.db.session import SessionLocal
from app.models.import_job import ImportJob
from app.services.import_service import import_folder

logger = get_logger(__name__)

# Thread pool for running sync folder imports (max 2 concurrent scans)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="import_folder")


def create_folder_import_job(folder_path: str) -> str:
    """Create a new pending job in the database and return job_id."""
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        job = ImportJob(
            job_id=job_id,
            job_type="folder",
            status="pending",
            folder_path=folder_path,
            progress=0,
            total=0,
        )
        db.add(job)
        db.commit()
        logger.info("Folder import job created", extra={"job_id": job_id, "folder_path": folder_path})
    except Exception:
        db.rollback()
        logger.exception("Failed to create folder import job")
    finally:
        db.close()
    return job_id


def get_import_job(job_id: str) -> dict | None:
    """Return job status dict if it exists, or None."""
    db = SessionLocal()
    try:
        stmt = select(ImportJob).where(ImportJob.job_id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if not job:
            return None
        return job.to_dict()
    finally:
        db.close()


def list_import_jobs(limit: int = 50) -> list[dict]:
    """Return most recent jobs (newest first) as dicts."""
    db = SessionLocal()
    try:
        stmt = (
            select(ImportJob)
            .order_by(ImportJob.created_at.desc())
            .limit(limit)
        )
        jobs = db.execute(stmt).scalars().all()
        return [j.to_dict() for j in jobs]
    finally:
        db.close()


def _run_folder_import_sync(job_id: str, folder_path: str) -> None:
    """
    Run folder import in a background thread. Uses its own DB session.
    Updates job status to running, then completed or failed.
    """
    db = SessionLocal()
    try:
        # Update to running
        stmt = select(ImportJob).where(ImportJob.job_id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if not job or job.status != "pending":
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("Background folder import started", extra={"job_id": job_id, "folder_path": folder_path})
        imported, folder = import_folder(db, folder_path, create_folder_record=True)
        db.commit()

        for s in imported:
            db.refresh(s)
        if folder:
            db.refresh(folder)

        # Update to completed
        result = {
            "imported_count": len(imported),
            "folder_id": folder.id if folder else None,
            "song_ids": [s.id for s in imported],
        }

        stmt = select(ImportJob).where(ImportJob.job_id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if job:
            job.status = "completed"
            job.progress = len(imported)
            job.total = len(imported)
            job.result_json = json.dumps(result)
            job.completed_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            db.commit()

        logger.info(
            "Background folder import completed",
            extra={"job_id": job_id, "imported_count": len(imported), "folder_id": folder.id if folder else None},
        )
    except Exception as e:
        db.rollback()
        logger.exception("Background folder import failed", extra={"job_id": job_id, "folder_path": folder_path})

        try:
            stmt = select(ImportJob).where(ImportJob.job_id == job_id)
            job = db.execute(stmt).scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error = str(e)
                job.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def schedule_folder_import(job_id: str, folder_path: str) -> None:
    """
    Schedule folder import to run in a background thread (fire-and-forget).
    Call from an async route so the event loop is available; returns immediately.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_in_executor(_executor, _run_folder_import_sync, job_id, folder_path)
