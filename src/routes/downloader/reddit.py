from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import requests
from ...auth.auth import verify_api_key
from typing import Dict

reddit_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


def fetch_reddit2(url: str) -> Dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    payload = {"url": url}
    session = requests.Session()
    response = session.post(
        "https://submagic-free-tools.fly.dev/api/reddit-download",
        headers=headers,
        json=payload,
    )
    data = response.json()
    # print(data, "data from reddit2")
    title = data["title"]
    thumbnail = data.get("thumbnailUrl", "")

    urls = []
    for item in data.get("videoFormats", []):
        urls.append(
            {
                "quality": item.get("quality", ""),
                "url": item.get("url", ""),
                "filesize": "",
            }
        )

    return {"title": title, "thumbnail": thumbnail, "videos": urls}


def fetch_redidown(url: str) -> Dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    session.get("https://redidown.com/", headers=headers)

    payload = {"url": url}
    response = session.post(
        "https://redidown.com/download", headers=headers, json=payload
    )
    data = response.json()
    # print(data, "data from redidown
    video_info = data.get("video_info", {})
    full_hd = video_info.get("full_hd", {})

    return {
        "title": video_info.get("title", ""),
        "thumbnail": "",
        "videos": [
            {"quality": "1080p", "url": full_hd.get("url", ""), "filesize": "null"}
        ],
    }


async def download_reddit_core(url: str):
    """
    Core Reddit download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Reddit video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """

    print(url, "url in reddit core")
    try:
        loop = asyncio.get_event_loop()
        task_reddit2 = loop.run_in_executor(None, fetch_reddit2, url)
        task_redidown = loop.run_in_executor(None, fetch_redidown, url)

        done, pending = await asyncio.wait(
            [task_reddit2, task_redidown], return_when=asyncio.FIRST_COMPLETED
        )

        first_result = None
        first_error = None
        for task in done:
            try:
                result = task.result()
                if result and isinstance(result, dict) and result.get("videos"):
                    first_result = result
                    break
            except Exception as e:
                first_error = e

        # If first completed task failed or returned error, wait for the other(s)
        if not first_result:
            if pending:
                more_done, _ = await asyncio.wait(pending)
                for task in more_done:
                    try:
                        result = task.result()
                        if result and isinstance(result, dict) and result.get("videos"):
                            first_result = result
                            break
                    except Exception as e:
                        first_error = e

        # Cancel any remaining tasks
        for task in pending:
            task.cancel()

        if first_result:
            return first_result
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Both Reddit download methods failed: {str(first_error) if first_error else 'Unknown error'}",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reddit download error: {str(e)}")


@reddit_router.get("/reddit/")
async def download_reddit_combined(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Reddit video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_reddit_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
