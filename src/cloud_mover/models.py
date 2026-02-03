"""Database models using SQLModel."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Backup(SQLModel, table=True):
    """Backup table for storing upload metadata."""

    __tablename__ = "backups"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=6)
    file_path: str
    file_size: int
    uploaded_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime
