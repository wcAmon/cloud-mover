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

    # Override upload directory
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
    assert "POST /register" in response.text


def test_register_returns_code(client: TestClient):
    """Register should return a 6-character code."""
    response = client.post("/register")
    assert response.status_code == 200

    data = response.json()
    assert "code" in data
    assert len(data["code"]) == 6
    assert data["code"].isalnum()


def test_upload_requires_valid_code(client: TestClient):
    """Upload should reject invalid code format."""
    file_content = b"test content"
    response = client.post(
        "/upload",
        data={"code": "invalid"},
        files={"file": ("test.zip", io.BytesIO(file_content), "application/zip")},
    )
    assert response.status_code == 400


def test_upload_requires_registered_code(client: TestClient):
    """Upload should reject unregistered code."""
    file_content = b"test content"
    response = client.post(
        "/upload",
        data={"code": "abc123"},
        files={"file": ("test.zip", io.BytesIO(file_content), "application/zip")},
    )
    assert response.status_code == 404


def test_full_upload_download_flow(client: TestClient):
    """Test complete upload and download flow."""
    # 1. Register
    reg_response = client.post("/register")
    assert reg_response.status_code == 200
    code = reg_response.json()["code"]

    # 2. Upload
    file_content = b"this is a test backup file content"
    upload_response = client.post(
        "/upload",
        data={"code": code},
        files={"file": ("backup.zip", io.BytesIO(file_content), "application/zip")},
    )
    assert upload_response.status_code == 200
    otp = upload_response.json()["otp"]
    assert len(otp) == 4

    # 3. Check status
    status_response = client.get(f"/status/{code}")
    assert status_response.status_code == 200
    assert status_response.json()["has_backup"] is True

    # 4. Download
    download_response = client.post(
        "/download",
        json={"code": code, "otp": otp},
    )
    assert download_response.status_code == 200
    assert download_response.content == file_content


def test_download_wrong_otp(client: TestClient):
    """Download should fail with wrong OTP."""
    # Register and upload
    reg_response = client.post("/register")
    code = reg_response.json()["code"]

    file_content = b"test content"
    client.post(
        "/upload",
        data={"code": code},
        files={"file": ("backup.zip", io.BytesIO(file_content), "application/zip")},
    )

    # Try download with wrong OTP
    download_response = client.post(
        "/download",
        json={"code": code, "otp": "0000"},
    )
    assert download_response.status_code == 404


def test_status_no_backup(client: TestClient):
    """Status should return has_backup=false for user without backup."""
    # Register but don't upload
    reg_response = client.post("/register")
    code = reg_response.json()["code"]

    status_response = client.get(f"/status/{code}")
    assert status_response.status_code == 200
    assert status_response.json()["has_backup"] is False
