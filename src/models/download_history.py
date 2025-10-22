from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class DownloadStatus(str, Enum):
    """Enum for download status"""

    SUCCESS = "success"
    FAILED = "failed"


class DownloadHistory(SQLModel, table=True):
    """
    Model for tracking video download history.

    Tracks all download requests with their status, response time,
    and error information if applicable.
    """

    __tablename__ = "download_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True, max_length=2048, description="Video URL requested")
    platform: str = Field(
        index=True,
        max_length=50,
        description="Platform detected (e.g., tiktok, instagram)",
    )
    status: DownloadStatus = Field(
        index=True, description="Download status: success or failed"
    )
    title: Optional[str] = Field(
        default=None, max_length=500, description="Video title if download succeeded"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error details if download failed"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        description="Timestamp when download was requested",
    )
    response_time: Optional[float] = Field(
        default=None, description="Processing time in seconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.tiktok.com/@user/video/123456789",
                "platform": "tiktok",
                "status": "success",
                "title": "Amazing TikTok Video",
                "error_message": None,
                "response_time": 2.34,
            }
        }
