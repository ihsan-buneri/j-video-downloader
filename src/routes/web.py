from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select, func, and_, case
from sqlalchemy import Integer
from typing import Optional

from ..database.database import get_session
from ..models.download_history import DownloadHistory, DownloadStatus

# Initialize templates
templates = Jinja2Templates(directory="templates")

web_router = APIRouter(tags=["Web Interface"])

# Platform icon mapping - all 19 platforms from general.py
PLATFORM_ICONS = {
    "tiktok": "🎵",
    "instagram": "📸",
    "facebook": "👥",
    "twitter": "🐦",
    "dailymotion": "🎬",
    "reddit": "🔴",
    "pinterest": "📌",
    "ninegag": "😂",
    "bitchute": "🎥",
    "douyin": "🇨🇳",
    "imdb": "🎭",
    "kwai": "📱",
    "linkedin": "💼",
    "rumble": "📹",
    "snapchat": "👻",
    "twitch": "🎮",
    "buzzfeed": "📰",
    "tumblr": "📝",
    "bilibili": "📺",
}

# Platform display names
PLATFORM_NAMES = {
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "Twitter",
    "dailymotion": "Dailymotion",
    "reddit": "Reddit",
    "pinterest": "Pinterest",
    "ninegag": "9GAG",
    "bitchute": "BitChute",
    "douyin": "Douyin",
    "imdb": "IMDb",
    "kwai": "Kwai",
    "linkedin": "LinkedIn",
    "rumble": "Rumble",
    "snapchat": "Snapchat",
    "twitch": "Twitch",
    "buzzfeed": "BuzzFeed",
    "tumblr": "Tumblr",
    "bilibili": "Bilibili",
}


def mask_api_key(api_key: str) -> str:
    """Mask API key for display, showing only first 4 and last 4 characters"""
    if len(api_key) <= 8:
        return "****" + api_key[-4:]
    return api_key[:4] + "****" + api_key[-4:]


def get_database_date_range(session: Session) -> dict:
    """
    Get the actual date range of data in the database.

    Args:
        session: Database session

    Returns:
        Dictionary with min_date, max_date, and count
    """
    try:
        statement = select(
            func.min(DownloadHistory.created_at).label("min_date"),
            func.max(DownloadHistory.created_at).label("max_date"),
            func.count(DownloadHistory.id).label("total_count"),
        )
        result = session.exec(statement).first()

        if result and result.total_count > 0:
            return {
                "min_date": result.min_date,
                "max_date": result.max_date,
                "total_count": result.total_count,
                "has_data": True,
            }
        return {"has_data": False, "total_count": 0}
    except Exception as e:
        print(f"Error getting database date range: {e}")
        return {"has_data": False, "total_count": 0}


def parse_period_to_dates(
    period: str, db_max_date: Optional[datetime] = None
) -> tuple[datetime, datetime]:
    """
    Convert period string to start and end datetime objects.
    Uses database's max date if available, otherwise uses current time.

    Args:
        period: One of "3days", "7days", "1month", "3months", "1year"
        db_max_date: Maximum date from database (optional)

    Returns:
        Tuple of (start_date, end_date)
    """
    # Use database max date if available, otherwise current time
    # Remove timezone to match database storage (which uses timezone.utc in Field but stores as naive)
    if db_max_date:
        end_date = (
            db_max_date.replace(tzinfo=None) if db_max_date.tzinfo else db_max_date
        )
    else:
        end_date = datetime.now()

    period_mapping = {
        "3days": 3,
        "7days": 7,
        "1month": 30,
        "3months": 90,
        "1year": 365,
    }

    days = period_mapping.get(period, 3)  # Default to 3 days
    start_date = end_date - timedelta(days=days)

    return start_date, end_date


def calculate_percentage_change(current: float, previous: float) -> dict:
    """
    Calculate percentage change between current and previous values.

    Args:
        current: Current period value
        previous: Previous period value

    Returns:
        Dictionary with change (percentage), direction ("positive"/"negative"), and display text
    """
    if previous == 0:
        if current > 0:
            return {"change": 100.0, "direction": "positive", "text": "↑ New data"}
        return {"change": 0.0, "direction": "neutral", "text": "No change"}

    change = ((current - previous) / previous) * 100

    if change > 0:
        return {
            "change": round(abs(change), 1),
            "direction": "positive",
            "text": f"↑ {round(abs(change), 1)}% from previous period",
        }
    elif change < 0:
        return {
            "change": round(abs(change), 1),
            "direction": "negative",
            "text": f"↓ {round(abs(change), 1)}% from previous period",
        }
    else:
        return {"change": 0.0, "direction": "neutral", "text": "No change"}


def get_stats_for_period(
    session: Session, start_date: datetime, end_date: datetime
) -> dict:
    """
    Get statistics for a specific period (helper function).

    Args:
        session: Database session
        start_date: Period start date
        end_date: Period end date

    Returns:
        Dictionary with basic stats
    """
    try:
        statement = select(
            func.count(DownloadHistory.id).label("total"),
            func.sum(
                case((DownloadHistory.status == DownloadStatus.SUCCESS, 1), else_=0)
            ).label("successful"),
            func.sum(
                case((DownloadHistory.status == DownloadStatus.FAILED, 1), else_=0)
            ).label("failed"),
            func.avg(DownloadHistory.response_time).label("avg_response_time"),
        ).where(
            and_(
                DownloadHistory.created_at >= start_date,
                DownloadHistory.created_at <= end_date,
            )
        )

        result = session.exec(statement).first()

        total = result.total if result and result.total else 0
        successful = result.successful if result and result.successful else 0
        failed = result.failed if result and result.failed else 0
        avg_response_time = (
            result.avg_response_time if result and result.avg_response_time else 0.0
        )
        success_rate = (successful / total) * 100 if total > 0 else 0.0

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
        }
    except Exception as e:
        print(f"Error getting stats for period: {e}")
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0.0,
            "avg_response_time": 0.0,
        }


def get_dashboard_stats(
    session: Session, start_date: datetime, end_date: datetime
) -> dict:
    """
    Get overall dashboard statistics with comparison to previous period.

    Args:
        session: Database session
        start_date: Filter start date
        end_date: Filter end date

    Returns:
        Dictionary with stats and percentage changes from previous period
    """
    try:
        # Get current period stats
        current_stats = get_stats_for_period(session, start_date, end_date)

        # Calculate previous period dates
        period_duration = end_date - start_date
        previous_end_date = start_date
        previous_start_date = previous_end_date - period_duration

        # Get previous period stats
        previous_stats = get_stats_for_period(
            session, previous_start_date, previous_end_date
        )

        # Calculate percentage changes
        total_change = calculate_percentage_change(
            current_stats["total"], previous_stats["total"]
        )
        successful_change = calculate_percentage_change(
            current_stats["successful"], previous_stats["successful"]
        )
        failed_change = calculate_percentage_change(
            current_stats["failed"], previous_stats["failed"]
        )
        success_rate_change = calculate_percentage_change(
            current_stats["success_rate"], previous_stats["success_rate"]
        )

        # For response time, lower is better, so invert the sentiment
        response_time_raw = calculate_percentage_change(
            current_stats["avg_response_time"], previous_stats["avg_response_time"]
        )
        if response_time_raw["direction"] == "positive":
            response_time_change = {
                "change": response_time_raw["change"],
                "direction": "negative",  # Slower is bad
                "text": f"↑ {response_time_raw['change']}% slower",
            }
        elif response_time_raw["direction"] == "negative":
            response_time_change = {
                "change": response_time_raw["change"],
                "direction": "positive",  # Faster is good
                "text": f"↓ {response_time_raw['change']}% faster",
            }
        else:
            response_time_change = response_time_raw

        # For failed, lower is better
        if failed_change["direction"] == "positive":
            failed_change["direction"] = "negative"  # More failures is bad
        elif failed_change["direction"] == "negative":
            failed_change["direction"] = "positive"  # Fewer failures is good

        return {
            "total_requests": current_stats["total"],
            "total_requests_change": total_change,
            "successful": current_stats["successful"],
            "successful_change": successful_change,
            "failed": current_stats["failed"],
            "failed_change": failed_change,
            "success_rate": round(current_stats["success_rate"], 1),
            "success_rate_change": success_rate_change,
            "avg_response_time": round(current_stats["avg_response_time"], 2),
            "avg_response_time_change": response_time_change,
        }
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        no_change = {"change": 0.0, "direction": "neutral", "text": "No data"}
        return {
            "total_requests": 0,
            "total_requests_change": no_change,
            "successful": 0,
            "successful_change": no_change,
            "failed": 0,
            "failed_change": no_change,
            "success_rate": 0.0,
            "success_rate_change": no_change,
            "avg_response_time": 0.0,
            "avg_response_time_change": no_change,
        }


def get_platform_statistics(
    session: Session, start_date: datetime, end_date: datetime
) -> list:
    """
    Get per-platform statistics from database.

    Args:
        session: Database session
        start_date: Filter start date
        end_date: Filter end date

    Returns:
        List of platform statistics with name, icon, total, success, failed, percentages
    """
    try:
        # Query platform breakdown
        statement = (
            select(
                DownloadHistory.platform,
                func.count(DownloadHistory.id).label("total"),
                func.sum(
                    case((DownloadHistory.status == DownloadStatus.SUCCESS, 1), else_=0)
                ).label("success"),
                func.sum(
                    case((DownloadHistory.status == DownloadStatus.FAILED, 1), else_=0)
                ).label("failed"),
            )
            .where(
                and_(
                    DownloadHistory.created_at >= start_date,
                    DownloadHistory.created_at <= end_date,
                )
            )
            .group_by(DownloadHistory.platform)
            .order_by(func.count(DownloadHistory.id).desc())
        )

        results = session.exec(statement).all()

        # Convert to list of dicts and add icons
        platforms_data = []
        max_count = 0

        for row in results:
            platform_key = row.platform.lower()
            total = row.total if row.total else 0
            success = row.success if row.success else 0
            failed = row.failed if row.failed else 0

            if total > max_count:
                max_count = total

            platforms_data.append(
                {
                    "name": PLATFORM_NAMES.get(platform_key, row.platform.title()),
                    "icon": PLATFORM_ICONS.get(platform_key, "🌐"),
                    "total": total,
                    "success": success,
                    "failed": failed,
                }
            )

        # If no data, show all platforms with 0 counts
        if not platforms_data:
            for platform_key, icon in PLATFORM_ICONS.items():
                platforms_data.append(
                    {
                        "name": PLATFORM_NAMES.get(platform_key, platform_key.title()),
                        "icon": icon,
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                    }
                )
            max_count = 1  # Avoid division by zero

        # Calculate percentages
        for platform in platforms_data:
            platform["total_percentage"] = (
                round((platform["total"] / max_count) * 100, 1) if max_count > 0 else 0
            )
            platform["success_percentage"] = (
                round((platform["success"] / max_count) * 100, 1)
                if max_count > 0
                else 0
            )
            platform["failed_percentage"] = (
                round((platform["failed"] / max_count) * 100, 1) if max_count > 0 else 0
            )

        return platforms_data

    except Exception as e:
        print(f"Error getting platform statistics: {e}")
        # Return all platforms with 0 counts on error
        return [
            {
                "name": PLATFORM_NAMES.get(key, key.title()),
                "icon": icon,
                "total": 0,
                "success": 0,
                "failed": 0,
                "total_percentage": 0,
                "success_percentage": 0,
                "failed_percentage": 0,
            }
            for key, icon in PLATFORM_ICONS.items()
        ]


def get_recent_downloads(
    session: Session, start_date: datetime, end_date: datetime, limit: int = 10
) -> list:
    """
    Get recent downloads from database.

    Args:
        session: Database session
        start_date: Filter start date
        end_date: Filter end date
        limit: Maximum number of records to return

    Returns:
        List of recent downloads with platform, title, url, status, response_time, date
    """
    try:
        statement = (
            select(DownloadHistory)
            .where(
                and_(
                    DownloadHistory.created_at >= start_date,
                    DownloadHistory.created_at <= end_date,
                )
            )
            .order_by(DownloadHistory.created_at.desc())
            .limit(limit)
        )

        results = session.exec(statement).all()

        recent_downloads = []
        for record in results:
            platform_key = record.platform.lower()
            recent_downloads.append(
                {
                    "platform": PLATFORM_NAMES.get(
                        platform_key, record.platform.title()
                    ),
                    "title": record.title if record.title else "Untitled",
                    "url": record.url,
                    "status": record.status.value,
                    "response_time": round(record.response_time, 2)
                    if record.response_time
                    else 0.0,
                    "date": record.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        return recent_downloads

    except Exception as e:
        print(f"Error getting recent downloads: {e}")
        return []


@web_router.get("/", response_class=HTMLResponse)
async def welcome_page(request: Request):
    """
    Render the welcome/landing page
    """
    return templates.TemplateResponse("welcome.html", {"request": request})


@web_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    api_key: str = "demo-key",
    period: str = "3days",
    session: Session = Depends(get_session),
):
    """
    Render the analytics dashboard with real data from database.

    Args:
        request: FastAPI request object
        api_key: API key from query parameter (for display purposes)
        period: Time period filter ("3days", "7days", "1month", "3months", "1year")
        session: Database session
    """
    # Get database date range first to use actual data dates
    db_range = get_database_date_range(session)

    # Parse period using actual database dates (fixes issue with future dates)
    start_date, end_date = parse_period_to_dates(
        period, db_range.get("max_date") if db_range.get("has_data") else None
    )

    # Get real data from database
    stats = get_dashboard_stats(session, start_date, end_date)
    platform_stats = get_platform_statistics(session, start_date, end_date)
    recent_downloads = get_recent_downloads(session, start_date, end_date, limit=10)

    # Mask the API key for display
    api_key_masked = mask_api_key(api_key)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "api_key_masked": api_key_masked,
            "stats": stats,
            "platform_stats": platform_stats,
            "recent_downloads": recent_downloads,
        },
    )
