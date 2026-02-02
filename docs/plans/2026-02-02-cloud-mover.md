# Cloud-Mover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立一個 Claude Code 搬家助手 API 服務，讓用戶可以在不同電腦間遷移 Claude Code 設定。

**Architecture:** FastAPI 後端 + SQLite 資料庫 + 本地檔案儲存。用戶透過 Claude Code 呼叫 API 上傳/下載設定壓縮檔，使用系統產生的 6 碼識別碼 + 4 位數字 OTP 驗證，24 小時後自動過期清理。

**Tech Stack:** Python 3.12, FastAPI, SQLModel, SQLite, uv

---

## Task 1: 專案初始化

**Files:**
- Create: `pyproject.toml`
- Create: `src/cloud_mover/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `CLAUDE.md`

**Step 1: 建立 pyproject.toml**

```toml
[project]
name = "cloud-mover"
version = "0.1.0"
description = "Claude Code Migration Helper API"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlmodel>=0.0.22",
    "python-multipart>=0.0.18",
    "pydantic-settings>=2.7.0",
]

[project.scripts]
cloud-mover = "cloud_mover.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cloud_mover"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Step 2: 建立 src/cloud_mover/__init__.py**

```python
"""Cloud-Mover: Claude Code Migration Helper API."""

__version__ = "0.1.0"
```

**Step 3: 建立 .env.example**

```env
# Cloud-Mover Configuration
HOST=0.0.0.0
PORT=8080
UPLOAD_DIR=./uploads
DATA_DIR=./data
MAX_FILE_SIZE_MB=59
OTP_EXPIRY_HOURS=24
```

**Step 4: 建立 .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
*.egg-info/

# Environment
.env

# Data
uploads/
data/
*.db

# IDE
.idea/
.vscode/
*.swp

# uv
.python-version
uv.lock
```

**Step 5: 建立 CLAUDE.md**

```markdown
# Cloud-Mover

Claude Code 搬家助手 API 服務。

## 快速指令

cd /home/cloud-mover
uv run cloud-mover          # 啟動服務
uv run pytest               # 執行測試

## API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | API 文件（給 Claude Code 閱讀） |
| `/register` | POST | 註冊取得識別碼 |
| `/upload` | POST | 上傳備份檔案 |
| `/download` | POST | 下載備份檔案 |

## 技術棧

- FastAPI + SQLModel + SQLite
- 本地檔案儲存（./uploads/）
- 24 小時自動過期清理
```

**Step 6: 建立目錄結構**

```bash
mkdir -p src/cloud_mover/services src/cloud_mover/routers uploads data tests
touch src/cloud_mover/services/__init__.py src/cloud_mover/routers/__init__.py
touch uploads/.gitkeep data/.gitkeep
```

**Step 7: 初始化 uv 並安裝依賴**

Run: `cd /home/cloud-mover && uv sync`
Expected: 依賴安裝成功

**Step 8: Commit**

```bash
git init
git add -A
git commit -m "feat: initialize cloud-mover project structure"
```

---

## Task 2: 設定管理與資料庫模型

**Files:**
- Create: `src/cloud_mover/config.py`
- Create: `src/cloud_mover/models.py`
- Create: `src/cloud_mover/database.py`

**Step 1: 建立 config.py**

```python
"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    host: str = "0.0.0.0"
    port: int = 8080
    upload_dir: Path = Path("./uploads")
    data_dir: Path = Path("./data")
    max_file_size_mb: int = 59
    otp_expiry_hours: int = 24

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def max_file_size_bytes(self) -> int:
        """Return max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def database_url(self) -> str:
        """Return SQLite database URL."""
        return f"sqlite:///{self.data_dir}/cloud_mover.db"


settings = Settings()
```

**Step 2: 建立 models.py**

```python
"""Database models using SQLModel."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User table for storing identification codes."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=6)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_ip: Optional[str] = Field(default=None, max_length=45)


class Backup(SQLModel, table=True):
    """Backup table for storing upload metadata."""

    __tablename__ = "backups"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    otp: str = Field(max_length=4)
    file_path: str
    file_size: Optional[int] = Field(default=None)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    uploaded_ip: Optional[str] = Field(default=None, max_length=45)
    expires_at: datetime


class ActionLog(SQLModel, table=True):
    """Action log table for tracking all operations."""

    __tablename__ = "action_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    action: str = Field(max_length=20)  # register, upload, download, cleanup
    ip: Optional[str] = Field(default=None, max_length=45)
    backup_id: Optional[int] = Field(default=None, foreign_key="backups.id")
    details: Optional[str] = Field(default=None)  # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Step 3: 建立 database.py**

```python
"""Database initialization and session management."""

from sqlmodel import Session, SQLModel, create_engine

from cloud_mover.config import settings

# Ensure data directory exists
settings.data_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Initialize database and create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yield a database session for dependency injection."""
    with Session(engine) as session:
        yield session
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add config, database models, and session management"
```

---

## Task 3: 認證服務（識別碼產生與驗證）

**Files:**
- Create: `src/cloud_mover/services/auth.py`
- Create: `tests/test_auth.py`

**Step 1: 建立 tests/test_auth.py**

```python
"""Tests for auth service."""

import pytest

from cloud_mover.services.auth import generate_code, generate_otp, is_valid_code


def test_generate_code_length():
    """Generated code should be 6 characters."""
    code = generate_code()
    assert len(code) == 6


def test_generate_code_alphanumeric():
    """Generated code should be alphanumeric lowercase."""
    code = generate_code()
    assert code.isalnum()
    assert code.islower()


def test_generate_code_unique():
    """Generated codes should be unique."""
    codes = {generate_code() for _ in range(100)}
    assert len(codes) == 100


def test_generate_otp_length():
    """Generated OTP should be 4 digits."""
    otp = generate_otp()
    assert len(otp) == 4


def test_generate_otp_digits():
    """Generated OTP should be digits only."""
    otp = generate_otp()
    assert otp.isdigit()


def test_is_valid_code_correct():
    """Valid code should pass validation."""
    assert is_valid_code("abc123") is True
    assert is_valid_code("xyz789") is True


def test_is_valid_code_wrong_length():
    """Code with wrong length should fail."""
    assert is_valid_code("abc") is False
    assert is_valid_code("abc12345") is False


def test_is_valid_code_invalid_chars():
    """Code with invalid characters should fail."""
    assert is_valid_code("ABC123") is False  # uppercase
    assert is_valid_code("abc-12") is False  # special char
```

**Step 2: 執行測試確認失敗**

Run: `cd /home/cloud-mover && uv run pytest tests/test_auth.py -v`
Expected: FAIL (module not found)

**Step 3: 建立 services/auth.py**

```python
"""Authentication service for code and OTP generation."""

import secrets
import string


def generate_code() -> str:
    """Generate a 6-character alphanumeric lowercase code."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def generate_otp() -> str:
    """Generate a 4-digit OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(4))


def is_valid_code(code: str) -> bool:
    """Validate code format: 6 alphanumeric lowercase characters."""
    if len(code) != 6:
        return False
    return code.isalnum() and code.islower()
```

**Step 4: 執行測試確認通過**

Run: `cd /home/cloud-mover && uv run pytest tests/test_auth.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: add auth service with code and OTP generation"
```

---

## Task 4: 備份服務（上傳/下載邏輯）

**Files:**
- Create: `src/cloud_mover/services/backup.py`
- Create: `src/cloud_mover/schemas.py`

**Step 1: 建立 schemas.py**

```python
"""Pydantic schemas for API request/response."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RegisterResponse(BaseModel):
    """Response for register endpoint."""

    code: str
    message: str = "註冊成功，請記住您的識別碼"


class UploadResponse(BaseModel):
    """Response for upload endpoint."""

    otp: str
    expires_at: datetime
    message: str = "上傳成功"


class DownloadRequest(BaseModel):
    """Request for download endpoint."""

    code: str
    otp: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str


class StatusResponse(BaseModel):
    """Response for status endpoint."""

    has_backup: bool
    expires_at: Optional[datetime] = None
    file_size: Optional[int] = None
```

**Step 2: 建立 services/backup.py**

```python
"""Backup service for file operations."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from cloud_mover.config import settings
from cloud_mover.models import ActionLog, Backup, User
from cloud_mover.services.auth import generate_code, generate_otp


def register_user(session: Session, ip: Optional[str] = None) -> User:
    """Register a new user with generated code."""
    # Generate unique code
    while True:
        code = generate_code()
        existing = session.exec(select(User).where(User.code == code)).first()
        if not existing:
            break

    user = User(code=code, created_ip=ip)
    session.add(user)
    session.commit()
    session.refresh(user)

    # Log action
    log = ActionLog(user_id=user.id, action="register", ip=ip)
    session.add(log)
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
    if existing:
        # Delete old file
        if os.path.exists(existing.file_path):
            os.remove(existing.file_path)
        session.delete(existing)

    otp = generate_otp()
    expires_at = datetime.utcnow() + timedelta(hours=settings.otp_expiry_hours)

    backup = Backup(
        user_id=user.id,
        otp=otp,
        file_path=file_path,
        file_size=file_size,
        uploaded_ip=ip,
        expires_at=expires_at,
    )
    session.add(backup)
    session.commit()
    session.refresh(backup)

    # Log action
    log = ActionLog(
        user_id=user.id,
        action="upload",
        ip=ip,
        backup_id=backup.id,
        details=json.dumps({"file_size": file_size}),
    )
    session.add(log)
    session.commit()

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
            Backup.expires_at > datetime.utcnow(),
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
            Backup.expires_at > datetime.utcnow(),
        )
    ).first()
```

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add backup service and API schemas"
```

---

## Task 5: 清理服務

**Files:**
- Create: `src/cloud_mover/services/cleanup.py`

**Step 1: 建立 services/cleanup.py**

```python
"""Cleanup service for expired backups."""

import json
import os
from datetime import datetime

from sqlmodel import Session, select

from cloud_mover.models import ActionLog, Backup


def cleanup_expired_backups(session: Session) -> int:
    """Delete expired backups and their files. Returns count of deleted items."""
    now = datetime.utcnow()

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
```

**Step 2: Commit**

```bash
git add -A
git commit -m "feat: add cleanup service for expired backups"
```

---

## Task 6: API 路由

**Files:**
- Create: `src/cloud_mover/routers/api.py`

**Step 1: 建立 routers/api.py**

```python
"""API routes for Cloud-Mover."""

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from cloud_mover.config import settings
from cloud_mover.database import get_session
from cloud_mover.schemas import (
    DownloadRequest,
    ErrorResponse,
    RegisterResponse,
    StatusResponse,
    UploadResponse,
)
from cloud_mover.services.auth import is_valid_code
from cloud_mover.services.backup import (
    create_backup,
    get_backup_for_download,
    get_backup_status,
    get_user_by_code,
    log_download,
    register_user,
)

router = APIRouter()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=RegisterResponse)
def register(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    """Register a new user and get an identification code."""
    ip = get_client_ip(request)
    user = register_user(session, ip)
    return RegisterResponse(code=user.code)


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def upload(
    request: Request,
    code: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
):
    """Upload a backup file."""
    ip = get_client_ip(request)

    # Validate code format
    if not is_valid_code(code):
        raise HTTPException(status_code=400, detail="識別碼格式錯誤")

    # Check user exists
    user = get_user_by_code(session, code)
    if not user:
        raise HTTPException(status_code=404, detail="識別碼不存在，請先註冊")

    # Check file size
    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"檔案大小超過限制 ({settings.max_file_size_mb}MB)",
        )

    # Save file
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{code}_{uuid.uuid4().hex[:8]}.zip"
    file_path = str(settings.upload_dir / filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    # Create backup record
    backup = create_backup(session, user, file_path, len(contents), ip)

    return UploadResponse(otp=backup.otp, expires_at=backup.expires_at)


@router.post(
    "/download",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def download(
    request: Request,
    body: DownloadRequest,
    session: Annotated[Session, Depends(get_session)],
):
    """Download a backup file."""
    ip = get_client_ip(request)

    # Validate code format
    if not is_valid_code(body.code):
        raise HTTPException(status_code=400, detail="識別碼格式錯誤")

    # Get backup
    backup = get_backup_for_download(session, body.code, body.otp)
    if not backup:
        raise HTTPException(status_code=404, detail="OTP 錯誤或已過期")

    # Check file exists
    if not os.path.exists(backup.file_path):
        raise HTTPException(status_code=404, detail="備份檔案不存在")

    # Log download
    log_download(session, backup, ip)

    return FileResponse(
        backup.file_path,
        media_type="application/zip",
        filename=f"claude-backup-{body.code}.zip",
    )


@router.get(
    "/status/{code}",
    response_model=StatusResponse,
    responses={400: {"model": ErrorResponse}},
)
def status(
    code: str,
    session: Annotated[Session, Depends(get_session)],
):
    """Check backup status for a user."""
    if not is_valid_code(code):
        raise HTTPException(status_code=400, detail="識別碼格式錯誤")

    backup = get_backup_status(session, code)
    if not backup:
        return StatusResponse(has_backup=False)

    return StatusResponse(
        has_backup=True,
        expires_at=backup.expires_at,
        file_size=backup.file_size,
    )
```

**Step 2: Commit**

```bash
git add -A
git commit -m "feat: add API routes for register, upload, download, status"
```

---

## Task 7: 主程式入口與 API 文件

**Files:**
- Create: `src/cloud_mover/main.py`

**Step 1: 建立 main.py（包含 API 文件）**

主程式包含：
- FastAPI 應用程式
- API 文件（給 Claude Code 閱讀）
- 定時清理任務
- Uvicorn 啟動入口

API 文件內容需明確指示 Claude Code：
1. 先詢問用戶是否有識別碼
2. 沒有則呼叫 /register 取得
3. 打包 ~/.claude/ 等設定檔
4. 上傳並告知用戶 OTP

**Step 2: 執行測試確認服務可啟動**

Run: `cd /home/cloud-mover && timeout 5 uv run cloud-mover || true`
Expected: 服務啟動，5 秒後 timeout 終止

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add main entry point with API documentation and cleanup task"
```

---

## Task 8: API 整合測試

**Files:**
- Create: `tests/test_api.py`
- Modify: `pyproject.toml` (新增 dev dependencies)

**Step 1: 新增 pytest 依賴到 pyproject.toml**

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
]
```

**Step 2: 建立 tests/test_api.py**

測試案例：
- test_root_returns_documentation
- test_register_returns_code
- test_upload_requires_valid_code
- test_upload_requires_registered_code
- test_full_upload_download_flow
- test_download_wrong_otp
- test_status_no_backup

**Step 3: 執行測試**

Run: `cd /home/cloud-mover && uv sync && uv run pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "test: add integration tests for API endpoints"
```

---

## Task 9: 建立 .env 並測試服務

**Files:**
- Create: `.env`

**Step 1: 建立 .env**

```env
HOST=0.0.0.0
PORT=8080
UPLOAD_DIR=./uploads
DATA_DIR=./data
MAX_FILE_SIZE_MB=59
OTP_EXPIRY_HOURS=24
```

**Step 2: 啟動服務測試**

Run: `cd /home/cloud-mover && uv run cloud-mover &`
Wait 3 seconds, then:
Run: `curl http://localhost:8080/`
Expected: 回傳 API 文件

**Step 3: 測試註冊**

Run: `curl -X POST http://localhost:8080/register`
Expected: `{"code":"xxxxxx","message":"註冊成功，請記住您的識別碼"}`

**Step 4: 停止服務**

Run: `pkill -f "cloud-mover"`

**Step 5: Commit**

```bash
git add .env
git commit -m "chore: add .env configuration"
```

---

## Task 10: Systemd 服務設定（可選）

**Files:**
- Create: `/etc/systemd/system/cloud-mover.service`（需 sudo）

**Step 1: 建立 systemd service 檔案**

```ini
[Unit]
Description=Cloud-Mover - Claude Code Migration Helper API
After=network-online.target

[Service]
Type=simple
User=wake
WorkingDirectory=/home/cloud-mover
EnvironmentFile=/home/cloud-mover/.env
ExecStart=/home/wake/.local/bin/uv run cloud-mover
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Step 2: 啟用服務**

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloud-mover
sudo systemctl start cloud-mover
sudo systemctl status cloud-mover
```

**Step 3: 更新 /home/CLAUDE.md**

將 cloud-mover 服務加入全域 CLAUDE.md。

---

## 完成

計畫完成後，服務將提供：
- `GET /` - API 文件（Claude Code 閱讀用）
- `POST /register` - 註冊取得識別碼
- `POST /upload` - 上傳備份
- `POST /download` - 下載備份
- `GET /status/{code}` - 查詢狀態
- 自動清理過期備份（每小時）
