"""Backup service for file operations."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from cloud_mover.config import settings
from cloud_mover.models import ActionLog, Backup, User
from cloud_mover.services.auth import generate_code, generate_otp

MAX_CODE_GENERATION_ATTEMPTS = 100


def register_user(session: Session, ip: Optional[str] = None) -> User:
    """Register a new user with generated code."""
    # Generate unique code with max attempts
    for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
        code = generate_code()
        existing = session.exec(select(User).where(User.code == code)).first()
        if not existing:
            break
    else:
        raise RuntimeError("Failed to generate unique code after max attempts")

    user = User(code=code, created_ip=ip)
    session.add(user)

    # Log action in same transaction
    log = ActionLog(user_id=None, action="register", ip=ip)
    session.add(log)

    session.commit()
    session.refresh(user)

    # Update log with user_id
    log.user_id = user.id
    session.commit()

    return user


def get_user_by_code(session: Session, code: str) -> Optional[User]:
    """Get user by identification code."""
    return session.exec(select(User).where(User.code == code)).first()


def create_backup(
    session: Session,
    user: User,
    file_path: str,
    file_size: int,
    ip: Optional[str] = None,
) -> Backup:
    """Create a new backup record."""
    # Delete any existing backup for this user
    existing = session.exec(
        select(Backup).where(Backup.user_id == user.id)
    ).first()

    old_file_path: Optional[str] = None
    if existing:
        old_file_path = existing.file_path
        session.delete(existing)

    otp = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.otp_expiry_hours)

    backup = Backup(
        user_id=user.id,
        otp=otp,
        file_path=file_path,
        file_size=file_size,
        uploaded_ip=ip,
        expires_at=expires_at,
    )
    session.add(backup)

    # Log action in same transaction
    log = ActionLog(
        user_id=user.id,
        action="upload",
        ip=ip,
        backup_id=None,
        details=json.dumps({"file_size": file_size}),
    )
    session.add(log)

    session.commit()
    session.refresh(backup)

    # Update log with backup_id
    log.backup_id = backup.id
    session.commit()

    # Delete old file after successful DB commit
    if old_file_path and os.path.exists(old_file_path):
        try:
            os.remove(old_file_path)
        except OSError:
            pass  # Best effort - file cleanup failure is non-critical

    return backup


def get_backup_for_download(
    session: Session, code: str, otp: str
) -> Optional[Backup]:
    """Get backup if code and OTP match and not expired."""
    user = get_user_by_code(session, code)
    if not user:
        return None

    backup = session.exec(
        select(Backup).where(
            Backup.user_id == user.id,
            Backup.otp == otp,
            Backup.expires_at > datetime.now(timezone.utc),
        )
    ).first()

    return backup


def log_download(
    session: Session,
    backup: Backup,
    ip: Optional[str] = None,
) -> None:
    """Log a download action."""
    log = ActionLog(
        user_id=backup.user_id,
        action="download",
        ip=ip,
        backup_id=backup.id,
        details=json.dumps({"source_ip": backup.uploaded_ip}),
    )
    session.add(log)
    session.commit()


def get_backup_status(session: Session, code: str) -> Optional[Backup]:
    """Get current backup status for a user."""
    user = get_user_by_code(session, code)
    if not user:
        return None

    return session.exec(
        select(Backup).where(
            Backup.user_id == user.id,
            Backup.expires_at > datetime.now(timezone.utc),
        )
    ).first()
