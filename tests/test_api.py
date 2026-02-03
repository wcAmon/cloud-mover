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
