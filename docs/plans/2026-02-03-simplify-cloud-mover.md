# Simplify Cloud-Mover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 簡化 Cloud-Mover 為單一驗證碼流程，用戶自設壓縮密碼，安裝說明放在 zip 內。

**Architecture:** 移除 User 表和 OTP 機制，Backup 表直接用 code 作為主要識別。上傳產生 code，下載只需 code。API 文件分上傳/下載情境教導 Claude Code 操作流程。

**Tech Stack:** FastAPI, SQLModel, SQLite, pydantic-settings

---

### Task 1: 更新 config.py 加入 BASE_URL

**Files:**
- Modify: `src/cloud_mover/config.py`

**Step 1: 修改 config.py**

```python
"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    host: str = "0.0.0.0"
    port: int = 8080
    base_url: str = "http://localhost:8080"  # 新增
    upload_dir: Path = Path("./uploads")
    data_dir: Path = Path("./data")
    max_file_size_mb: int = 59
    expiry_hours: int = 24  # 重命名 otp_expiry_hours

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

**Step 2: Commit**

Run: `git add src/cloud_mover/config.py && git commit -m "feat: add base_url config, rename otp_expiry_hours to expiry_hours"`

---

### Task 2: 簡化 models.py - 移除 User 表

**Files:**
- Modify: `src/cloud_mover/models.py`

**Step 1: 重寫 models.py**

```python
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
```

**Step 2: Commit**

Run: `git add src/cloud_mover/models.py && git commit -m "feat: simplify models - remove User table, add code to Backup"`

---

### Task 3: 簡化 schemas.py

**Files:**
- Modify: `src/cloud_mover/schemas.py`

**Step 1: 重寫 schemas.py**

```python
"""Pydantic schemas for API request/response."""

from datetime import datetime

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response for upload endpoint."""

    code: str = Field(min_length=6, max_length=6)
    expires_at: datetime
    message: str = "上傳成功，請記住驗證碼"


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
```

**Step 2: Commit**

Run: `git add src/cloud_mover/schemas.py && git commit -m "feat: simplify schemas - remove register/status/download schemas"`

---

### Task 4: 簡化 auth.py - 移除 OTP 相關

**Files:**
- Modify: `src/cloud_mover/services/auth.py`

**Step 1: 重寫 auth.py**

```python
"""Authentication service for code generation."""

import secrets
import string


def generate_code() -> str:
    """Generate a 6-character alphanumeric lowercase code."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def is_valid_code(code: str) -> bool:
    """Validate code format: 6 alphanumeric lowercase characters."""
    if len(code) != 6:
        return False
    return code.isalnum() and code.islower()
```

**Step 2: Commit**

Run: `git add src/cloud_mover/services/auth.py && git commit -m "feat: simplify auth - remove OTP generation"`

---

### Task 5: 重寫 backup.py 服務

**Files:**
- Modify: `src/cloud_mover/services/backup.py`

**Step 1: 重寫 backup.py**

```python
"""Backup service for file operations."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from cloud_mover.config import settings
from cloud_mover.models import Backup
from cloud_mover.services.auth import generate_code

MAX_CODE_GENERATION_ATTEMPTS = 100


def create_backup(
    session: Session,
    file_path: str,
    file_size: int,
) -> Backup:
    """Create a new backup record with unique code."""
    # Generate unique code
    for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
        code = generate_code()
        existing = session.exec(select(Backup).where(Backup.code == code)).first()
        if not existing:
            break
    else:
        raise RuntimeError("Failed to generate unique code after max attempts")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.expiry_hours)

    backup = Backup(
        code=code,
        file_path=file_path,
        file_size=file_size,
        expires_at=expires_at,
    )
    session.add(backup)
    session.commit()
    session.refresh(backup)

    return backup


def get_backup_by_code(session: Session, code: str) -> Optional[Backup]:
    """Get backup by code if not expired."""
    return session.exec(
        select(Backup).where(
            Backup.code == code,
            Backup.expires_at > datetime.now(timezone.utc),
        )
    ).first()
```

**Step 2: Commit**

Run: `git add src/cloud_mover/services/backup.py && git commit -m "feat: simplify backup service - remove user dependency"`

---

### Task 6: 重寫 cleanup.py

**Files:**
- Modify: `src/cloud_mover/services/cleanup.py`

**Step 1: 重寫 cleanup.py**

```python
"""Cleanup service for expired backups."""

import os
from datetime import datetime, timezone

from sqlmodel import Session, select

from cloud_mover.models import Backup


def cleanup_expired_backups(session: Session) -> int:
    """Delete expired backups and their files. Returns count of deleted items."""
    now = datetime.now(timezone.utc)

    expired = session.exec(select(Backup).where(Backup.expires_at < now)).all()

    count = 0
    for backup in expired:
        if os.path.exists(backup.file_path):
            try:
                os.remove(backup.file_path)
            except OSError:
                pass
        session.delete(backup)
        count += 1

    if count > 0:
        session.commit()

    return count
```

**Step 2: Commit**

Run: `git add src/cloud_mover/services/cleanup.py && git commit -m "feat: simplify cleanup - remove ActionLog"`

---

### Task 7: 重寫 API 路由

**Files:**
- Modify: `src/cloud_mover/routers/api.py`

**Step 1: 重寫 api.py**

```python
"""API routes for Cloud-Mover."""

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from cloud_mover.config import settings
from cloud_mover.database import get_session
from cloud_mover.schemas import ErrorResponse, UploadResponse
from cloud_mover.services.auth import is_valid_code
from cloud_mover.services.backup import create_backup, get_backup_by_code

router = APIRouter()


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={400: {"model": ErrorResponse}},
)
async def upload(
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
):
    """Upload a backup file and get a verification code."""
    contents = await file.read()
    if len(contents) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"檔案大小超過限制 ({settings.max_file_size_mb}MB)",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.zip"
    file_path = str(settings.upload_dir / filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    backup = create_backup(session, file_path, len(contents))

    return UploadResponse(code=backup.code, expires_at=backup.expires_at)


@router.get(
    "/download/{code}",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def download(
    code: str,
    session: Annotated[Session, Depends(get_session)],
):
    """Download a backup file using verification code."""
    if not is_valid_code(code):
        raise HTTPException(status_code=400, detail="驗證碼格式錯誤")

    backup = get_backup_by_code(session, code)
    if not backup:
        raise HTTPException(status_code=404, detail="驗證碼不存在或已過期")

    if not os.path.exists(backup.file_path):
        raise HTTPException(status_code=404, detail="備份檔案不存在")

    return FileResponse(
        backup.file_path,
        media_type="application/zip",
        filename=f"claude-backup-{code}.zip",
    )
```

**Step 2: Commit**

Run: `git add src/cloud_mover/routers/api.py && git commit -m "feat: simplify API - remove register/status, simplify upload/download"`

---

### Task 8: 重寫 main.py 的 API 文件

**Files:**
- Modify: `src/cloud_mover/main.py`

**Step 1: 重寫 main.py**

```python
"""Cloud-Mover FastAPI application."""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from cloud_mover.config import settings
from cloud_mover.database import engine, init_db
from cloud_mover.routers import api
from cloud_mover.services.cleanup import cleanup_expired_backups


def get_api_documentation() -> str:
    """Generate API documentation with current base_url."""
    return f"""# Cloud-Mover API

Claude Code 搬家助手。在不同電腦間遷移 Claude Code 設定。

服務網址：{settings.base_url}

---

## 上傳端（來源電腦）

你正在幫助用戶將 Claude Code 設定搬到新電腦。

### 步驟 1：準備安裝說明

建立 `INSTALL.md` 檔案，內容包含：
- 此備份包含哪些設定（settings.json、keybindings.json、plugins 等）
- 各檔案應該放置的位置
- plugins 需要的額外安裝步驟（如有）

範例 INSTALL.md：
```markdown
# Claude Code 搬家安裝說明

## 包含內容
- settings.json - 用戶設定
- keybindings.json - 快捷鍵設定
- plugins/ - 已安裝的 plugins

## 安裝步驟
1. 解壓縮到 ~/.claude/
2. 重啟 Claude Code

## plugins 說明
- my-plugin: 需要執行 `npm install` 安裝依賴
```

### 步驟 2：打包檔案

將以下內容打包成 zip（依實際存在的檔案）：
- `~/.claude/settings.json`
- `~/.claude/keybindings.json`
- `~/.claude/plugins/`
- `INSTALL.md`（你剛建立的）

**重要**：請用戶設定一個壓縮密碼保護檔案內容。

### 步驟 3：上傳

```
POST {settings.base_url}/upload
Content-Type: multipart/form-data
file: <zip 檔案>
```

回應：
```json
{{{{
  "code": "a7x9k2",
  "expires_at": "2026-02-04T12:00:00Z",
  "message": "上傳成功，請記住驗證碼"
}}}}
```

### 步驟 4：告知用戶

請告訴用戶：
- 驗證碼：`a7x9k2`（6 碼）
- 壓縮密碼：用戶自己設定的
- 有效期限：24 小時

用戶需要在新電腦上提供這兩組資訊。

---

## 下載端（目標電腦）

你正在幫助用戶從舊電腦接收 Claude Code 設定。

### 步驟 1：取得資訊

向用戶索取：
1. **驗證碼**（6 碼英數字）
2. **壓縮密碼**（用戶在舊電腦設定的）

### 步驟 2：下載

```
GET {settings.base_url}/download/{{{{code}}}}
```

回應：zip 檔案串流

### 步驟 3：解壓縮

使用用戶提供的壓縮密碼解壓縮檔案。

### 步驟 4：依照 INSTALL.md 安裝

讀取解壓後的 `INSTALL.md`，依照說明：
1. 將檔案放到正確位置（通常是 `~/.claude/`）
2. 執行必要的額外步驟（如 plugin 依賴安裝）
3. 提示用戶重啟 Claude Code

---

## API 參考

### POST /upload

上傳備份檔案，取得驗證碼。

**Request:** multipart/form-data
- `file`: zip 檔案（最大 {settings.max_file_size_mb}MB）

**Response:**
```json
{{{{
  "code": "a7x9k2",
  "expires_at": "2026-02-04T12:00:00Z",
  "message": "上傳成功，請記住驗證碼"
}}}}
```

### GET /download/{{{{code}}}}

使用驗證碼下載備份檔案。

**Response:** application/zip

**錯誤：**
- 400: 驗證碼格式錯誤
- 404: 驗證碼不存在或已過期
""".strip()


async def periodic_cleanup():
    """Run cleanup every hour."""
    while True:
        await asyncio.sleep(3600)
        with Session(engine) as session:
            count = cleanup_expired_backups(session)
            if count > 0:
                print(f"Cleaned up {{count}} expired backups")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    with Session(engine) as session:
        cleanup_expired_backups(session)

    cleanup_task = asyncio.create_task(periodic_cleanup())

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Cloud-Mover",
    description="Claude Code Migration Helper API",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(api.router)


@app.get("/", response_class=PlainTextResponse)
def root():
    """Return API documentation for Claude Code to read."""
    return get_api_documentation()


def main():
    """Run the application."""
    uvicorn.run(
        "cloud_mover.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

Run: `git add src/cloud_mover/main.py && git commit -m "feat: rewrite API docs for upload/download scenarios"`

---

### Task 9: 重寫測試

**Files:**
- Modify: `tests/test_auth.py`
- Modify: `tests/test_api.py`

**Step 1: 重寫 test_auth.py**

```python
"""Tests for auth service."""

from cloud_mover.services.auth import generate_code, is_valid_code


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
    assert is_valid_code("ABC123") is False
    assert is_valid_code("abc-12") is False
```

**Step 2: 重寫 test_api.py**

```python
"""Integration tests for API endpoints."""

import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from cloud_mover.database import get_session
from cloud_mover.main import app


@pytest.fixture(name="session")
def session_fixture():
    """Create a test database session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session, tmp_path):
    """Create a test client with dependency overrides."""
    from cloud_mover import config

    original_upload_dir = config.settings.upload_dir
    config.settings.upload_dir = tmp_path / "uploads"
    config.settings.upload_dir.mkdir(parents=True, exist_ok=True)

    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    config.settings.upload_dir = original_upload_dir


def test_root_returns_documentation(client: TestClient):
    """Root endpoint should return API documentation."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Cloud-Mover API" in response.text
    assert "POST /upload" in response.text
    assert "GET /download" in response.text


def test_upload_returns_code(client: TestClient):
    """Upload should return a 6-character code."""
    file_content = b"test backup content"
    response = client.post(
        "/upload",
        files={"file": ("backup.zip", io.BytesIO(file_content), "application/zip")},
    )
    assert response.status_code == 200

    data = response.json()
    assert "code" in data
    assert len(data["code"]) == 6
    assert data["code"].isalnum()
    assert "expires_at" in data


def test_upload_rejects_large_file(client: TestClient):
    """Upload should reject files exceeding size limit."""
    from cloud_mover import config

    original_max = config.settings.max_file_size_mb
    config.settings.max_file_size_mb = 0  # Set to 0 MB for test

    file_content = b"x" * 1024  # 1KB file
    response = client.post(
        "/upload",
        files={"file": ("backup.zip", io.BytesIO(file_content), "application/zip")},
    )
    assert response.status_code == 400

    config.settings.max_file_size_mb = original_max


def test_full_upload_download_flow(client: TestClient):
    """Test complete upload and download flow."""
    file_content = b"this is a test backup file content"

    # Upload
    upload_response = client.post(
        "/upload",
        files={"file": ("backup.zip", io.BytesIO(file_content), "application/zip")},
    )
    assert upload_response.status_code == 200
    code = upload_response.json()["code"]

    # Download
    download_response = client.get(f"/download/{code}")
    assert download_response.status_code == 200
    assert download_response.content == file_content


def test_download_invalid_code_format(client: TestClient):
    """Download should reject invalid code format."""
    response = client.get("/download/invalid")
    assert response.status_code == 400


def test_download_nonexistent_code(client: TestClient):
    """Download should return 404 for nonexistent code."""
    response = client.get("/download/abc123")
    assert response.status_code == 404
```

**Step 3: 執行測試**

Run: `uv run pytest -v`

**Step 4: Commit**

Run: `git add tests/test_auth.py tests/test_api.py && git commit -m "test: rewrite tests for simplified API"`

---

### Task 10: 更新 README.md 和 CLAUDE.md

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: 重寫 README.md**

```markdown
# Cloud-Mover

Claude Code 搬家助手 API 服務。

## 功能

- 上傳備份檔案，取得 6 碼驗證碼
- 使用驗證碼下載備份檔案
- 24 小時後自動刪除（檔案 + 記錄）

## 隱私保護

- 伺服器不儲存壓縮密碼，只有用戶知道
- 過期後完全刪除，不保留任何記錄
- 驗證碼僅用於識別檔案，無法解密內容

## 安裝

```bash
uv sync
```

## 設定

建立 `.env` 檔案：

```env
HOST=0.0.0.0
PORT=8080
BASE_URL=https://your-domain.com
MAX_FILE_SIZE_MB=59
EXPIRY_HOURS=24
```

## 啟動

```bash
uv run cloud-mover
```

## API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | API 使用說明（給 Claude Code 閱讀） |
| `/upload` | POST | 上傳備份，回傳驗證碼 |
| `/download/{code}` | GET | 使用驗證碼下載備份 |
```

**Step 2: 重寫 CLAUDE.md**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

```bash
uv run cloud-mover          # Start API server
uv run pytest               # Run all tests
uv run pytest tests/test_api.py::test_full_upload_download_flow  # Run single test
```

## Architecture

Cloud-Mover is a file transfer API for migrating Claude Code settings between machines.

### Flow

```
Upload(file) → code (6 chars, 24hr expiry)
Download(code) → file
```

User sets their own zip password for content protection. Server only stores code + file path.

### Module Structure

- `main.py` - FastAPI app, API documentation (context-aware for upload/download scenarios)
- `routers/api.py` - Endpoints: `/upload`, `/download/{code}`
- `services/auth.py` - Code generation and validation
- `services/backup.py` - Backup CRUD operations
- `services/cleanup.py` - Expired backup deletion
- `models.py` - SQLModel: Backup table only
- `schemas.py` - Pydantic response models
- `config.py` - Settings via pydantic-settings
- `database.py` - SQLite engine and session

### Key Behaviors

- Backups expire after 24 hours (configurable via `EXPIRY_HOURS`)
- File limit: 59MB (configurable via `MAX_FILE_SIZE_MB`)
- Expired backups fully deleted (file + DB record) for privacy
- `BASE_URL` in .env for API documentation
```

**Step 3: Commit**

Run: `git add README.md CLAUDE.md && git commit -m "docs: update README and CLAUDE.md for simplified API"`

---

### Task 11: 建立 .env.example

**Files:**
- Create: `.env.example`

**Step 1: 建立 .env.example**

```env
HOST=0.0.0.0
PORT=8080
BASE_URL=https://your-domain.com
MAX_FILE_SIZE_MB=59
EXPIRY_HOURS=24
```

**Step 2: Commit**

Run: `git add .env.example && git commit -m "chore: add .env.example"`

---

### Task 12: 清理並驗證

**Step 1: 刪除舊資料庫**

Run: `rm -rf data/ uploads/`

**Step 2: 執行完整測試**

Run: `uv run pytest -v`

Expected: All tests pass

**Step 3: Final commit**

Run: `git add -A && git commit -m "chore: cleanup and verify simplified Cloud-Mover" --allow-empty`
