"""
Import API: POST /import/file, POST /import/folder (async), GET /import/folder/status/{job_id}, GET /import/folder/jobs.
Folder import runs as a background task; single-file import remains synchronous.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging_config import get_logger
from app.db.session import get_db
from app.services.import_service import import_single_file, import_folder
from app.services.import_tasks import (
    create_folder_import_job,
    get_import_job,
    list_import_jobs,
    schedule_folder_import,
)
from app.schemas.song import SongResponse

router = APIRouter()
logger = get_logger(__name__)


class ImportFileBody(BaseModel):
    file_path: str


class ImportFolderBody(BaseModel):
    folder_path: str


@router.post("/file", response_model=SongResponse)
def import_file_route(body: ImportFileBody, db: Session = Depends(get_db)):
    """
    Import a single audio file by path. Synchronous; returns when the file is imported.
    """
    logger.info("Import file requested", extra={"file_path": body.file_path})
    song = import_single_file(db, body.file_path)
    if song is None:
        raise BadRequestError(
            "File not found, unsupported format, or already imported (duplicate path)",
            code="IMPORT_FAILED",
            details={"file_path": body.file_path},
        )
    db.commit()
    db.refresh(song)
    logger.info("File imported", extra={"song_id": song.id, "title": song.title})
    return song


@router.post("/folder")
async def import_folder_route(body: ImportFolderBody):
    """
    Start a background folder scan. Returns 202 Accepted immediately with a job_id.
    Poll GET /import/folder/status/{job_id} for progress and result.
    """
    folder_path = body.folder_path.strip()
    if not folder_path:
        raise BadRequestError("folder_path must be non-empty", code="VALIDATION_ERROR")
    logger.info("Folder import requested (background)", extra={"folder_path": folder_path})
    job_id = create_folder_import_job(folder_path)
    schedule_folder_import(job_id, folder_path)
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "accepted",
            "message": "Folder scan started; poll /import/folder/status/{job_id} for result.",
            "folder_path": folder_path,
        },
    )


@router.get("/folder/status/{job_id}")
def get_folder_import_status(job_id: str):
    """
    Get status and result of a folder import job.
    Returns 404 if job_id is unknown.
    """
    job = get_import_job(job_id)
    if not job:
        raise NotFoundError("Import job not found", resource="import_job", resource_id=job_id)
    return job.to_dict()


@router.get("/folder/jobs")
def list_folder_import_jobs(limit: int = 50):
    """
    List recent folder import jobs (newest first). Max limit 100.
    """
    jobs = list_import_jobs(limit=min(limit, 100))
    return {"jobs": [j.to_dict() for j in jobs], "count": len(jobs)}
