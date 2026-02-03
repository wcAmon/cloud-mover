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
