"""
ImportJob model: persistent tracking for background import/download jobs.
Replaces in-memory dict so jobs survive server restarts.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdCreatedUpdatedMixin


class ImportJob(Base, IdCreatedUpdatedMixin):
    __tablename__ = "import_jobs"

    job_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="folder")  # folder | spotify_download
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending | running | completed | failed
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    folder_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "folder_path": self.folder_path,
            "result_json": self.result_json,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __repr__(self) -> str:
        return f"<ImportJob(id={self.id}, job_id={self.job_id!r}, status={self.status!r})>"
