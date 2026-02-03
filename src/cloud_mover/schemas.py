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
