"""Cleanup service for expired backups."""

import json
import os
from datetime import datetime, timezone

from sqlmodel import Session, select

from cloud_mover.models import ActionLog, Backup


def cleanup_expired_backups(session: Session) -> int:
    """Delete expired backups and their files. Returns count of deleted items."""
    now = datetime.now(timezone.utc)

    # Find expired backups
    expired = session.exec(select(Backup).where(Backup.expires_at < now)).all()

    count = 0
    for backup in expired:
        # Delete file
        if os.path.exists(backup.file_path):
            try:
                os.remove(backup.file_path)
            except OSError:
                pass  # File might already be deleted

        # Delete record
        session.delete(backup)
        count += 1

    if count > 0:
        session.commit()

        # Log cleanup action
        log = ActionLog(
            action="cleanup",
            details=json.dumps({"deleted_count": count}),
        )
        session.add(log)
        session.commit()

    return count
