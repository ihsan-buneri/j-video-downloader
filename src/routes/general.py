from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import re
import time
from typing import Dict, Any, Optional
from sqlmodel import Session

from ..auth.auth import verify_api_key
from ..database.database import get_session
from ..models.download_history import DownloadHistory, DownloadStatus

# Import all core download functions
from .downloader.tiktok import download_tiktok_core
from .downloader.instagram import download_instagram_core
from .downloader.facebook import download_facebook_core
from .downloader.twitter import download_twitter_core
from .downloader.dailymotion import download_dailymotion_core
from .downloader.reddit import download_reddit_core
from .downloader.pinterest import download_pinterest_core
from .downloader.ninegag import download_9gag_core
from .downloader.bitchute import download_bitchute_core
from .downloader.douyin import download_douyin_core
from .downloader.imdb import download_imdb_core
from .downloader.kwai import download_kwai_core
from .downloader.linkedin import download_linkedin_core
from .downloader.rumble import download_rumble_core
from .downloader.snapchat import download_snapchat_core
from .downloader.twitch import download_twitch_core
from .downloader.buzzfeed import download_buzzfeed_core
from .downloader.tumblr import download_tumblr_core
from .downloader.bilibili import download_bilibili_core

general_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)

# Platform detection patterns
PLATFORM_PATTERNS = {
    "tiktok": [
        r"tiktok\.com",
        r"vm\.tiktok\.com",
        r"vt\.tiktok\.com",
        r"m\.tiktok\.com",
    ],
    "instagram": [r"instagram\.com", r"instagr\.am", r"ig\.me"],
    "facebook": [r"facebook\.com", r"fb\.com", r"fb\.watch"],
    "twitter": [
        r"(?:https?:\/\/)?(?:www\.)?twitter\.com\/",
        r"(?:https?:\/\/)?(?:www\.)?x\.com\/",
        r"(?:https?:\/\/)?(?:www\.)?t\.co\/",
    ],
    "dailymotion": [r"dailymotion\.com", r"dai\.ly"],
    "reddit": [
        r"reddit\.com",
        r"redd\.it",
        r"reddit\.com\/user\/",  # Add user profile pattern
        r"reddit\.com\/comments\/",  # Add comments pattern
    ],
    "pinterest": [r"pinterest\.com", r"pin\.it"],
    "ninegag": [r"9gag\.com"],
    "bitchute": [r"bitchute\.com"],
    "douyin": [r"douyin\.com"],
    "imdb": [r"imdb\.com"],
    "kwai": [r"kwai\.com"],
    "linkedin": [r"linkedin\.com"],
    "rumble": [r"rumble\.com"],
    "snapchat": [r"snapchat\.com"],
    "twitch": [r"twitch\.tv"],
    "buzzfeed": [r"buzzfeed\.com"],
    "tumblr": [r"tumblr\.com"],
    "bilibili": [r"bilibili\.com"],
}

# Core download functions mapping
DOWNLOAD_FUNCTIONS = {
    "tiktok": download_tiktok_core,
    "instagram": download_instagram_core,
    "facebook": download_facebook_core,
    "twitter": download_twitter_core,
    "dailymotion": download_dailymotion_core,
    "reddit": download_reddit_core,
    "pinterest": download_pinterest_core,
    "ninegag": download_9gag_core,
    "bitchute": download_bitchute_core,
    "douyin": download_douyin_core,
    "imdb": download_imdb_core,
    "kwai": download_kwai_core,
    "linkedin": download_linkedin_core,
    "rumble": download_rumble_core,
    "snapchat": download_snapchat_core,
    "twitch": download_twitch_core,
    "buzzfeed": download_buzzfeed_core,
    "tumblr": download_tumblr_core,
    "bilibili": download_bilibili_core,
}


def detect_platform(url: str) -> Optional[str]:
    """
    Detect the platform from the given URL.

    Args:
        url (str): The video URL to analyze

    Returns:
        Optional[str]: The detected platform name or None if not supported
    """
    url_lower = url.lower()

    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return platform

    return None


async def download_general_core(
    url: str, platform: Optional[str] = None, session: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Core general download logic that automatically detects platform and uses appropriate downloader.

    Args:
        url (str): Video URL to download
        platform (Optional[str]): Force specific platform (optional)
        session (Optional[Session]): Database session for tracking

    Returns:
        Dict[str, Any]: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If platform is not supported or download fails
    """
    start_time = time.time()
    detected_platform = platform

    try:
        # Detect platform if not provided
        if not detected_platform:
            detected_platform = detect_platform(url)

        if not detected_platform:
            error_msg = "Unsupported platform. Please provide a valid video URL from a supported platform."
            # Track failed attempt
            if session:
                try:
                    history_entry = DownloadHistory(
                        url=url,
                        platform="unknown",
                        status=DownloadStatus.FAILED,
                        error_message=error_msg,
                        response_time=time.time() - start_time,
                    )
                    session.add(history_entry)
                    session.commit()
                except Exception as db_error:
                    print(f"Failed to save history: {db_error}")

            raise HTTPException(status_code=400, detail=error_msg)

        # Check if platform is supported
        if detected_platform not in DOWNLOAD_FUNCTIONS:
            error_msg = f"Platform '{detected_platform}' is not supported yet."
            # Track failed attempt
            if session:
                try:
                    history_entry = DownloadHistory(
                        url=url,
                        platform=detected_platform,
                        status=DownloadStatus.FAILED,
                        error_message=error_msg,
                        response_time=time.time() - start_time,
                    )
                    session.add(history_entry)
                    session.commit()
                except Exception as db_error:
                    print(f"Failed to save history: {db_error}")

            raise HTTPException(status_code=400, detail=error_msg)

        # Get the appropriate download function
        download_func = DOWNLOAD_FUNCTIONS[detected_platform]

        # Call the platform-specific download function
        result = await download_func(url)

        # Track successful download
        if session:
            try:
                history_entry = DownloadHistory(
                    url=url,
                    platform=detected_platform,
                    status=DownloadStatus.SUCCESS,
                    title=result.get("title", ""),
                    response_time=time.time() - start_time,
                )
                session.add(history_entry)
                session.commit()
            except Exception as db_error:
                print(f"Failed to save history: {db_error}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Download error: {str(e)}"

        # Track failed download
        if session:
            try:
                history_entry = DownloadHistory(
                    url=url,
                    platform=detected_platform or "unknown",
                    status=DownloadStatus.FAILED,
                    error_message=str(e),
                    response_time=time.time() - start_time,
                )
                session.add(history_entry)
                session.commit()
            except Exception as db_error:
                print(f"Failed to save history: {db_error}")

        raise HTTPException(status_code=500, detail=error_msg)


@general_router.get("/common/")
async def download_general_auto(
    url: str,
    platform: Optional[str] = None,
    api_key: str = Depends(verify_api_key),
    session: Session = Depends(get_session),
):
    """
    General video download endpoint that automatically detects platform.

    Args:
        url (str): Video URL to download
        platform (Optional[str]): Force specific platform (optional)
        api_key (str): API key for authentication
        session (Session): Database session for tracking download history

    Returns:
        JSONResponse: Video information including title, thumbnail, and download links
    """
    try:
        result = await download_general_core(url, platform, session)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
