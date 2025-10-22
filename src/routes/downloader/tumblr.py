from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import requests
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key
from typing import Dict

tumblr_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


def fetch_tumblr2(url: str) -> Dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    payload = {"videoUrl": url}
    session = requests.Session()
    response = session.post(
        "https://a2z.tools/api/fetch-video-info", headers=headers, json=payload
    )
    data = response.json()

    title = data.get("title", "")
    thumbnail = data.get("thumbnail", "")
    video_url = data.get("formats", [{}])[0].get("url", "")

    return {
        "title": title,
        "thumbnail": thumbnail,
        "videos": [{"url": video_url, "quality": "1080p", "filesize": ""}],
    }


def fetch_savetumblr(url: str) -> Dict:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    init_response = session.get("https://savetumblr.com", headers=headers)

    soup = BeautifulSoup(init_response.text, "html.parser")
    token_meta = soup.find("meta", {"name": "csrf-token"})
    if not token_meta or not token_meta.get("content"):
        raise Exception("CSRF token not found on savetumblr.com")

    token = token_meta["content"]

    payload = {"_token": token, "url": url, "local": "vi"}
    response = session.post("https://savetumblr.com/", json=payload, headers=headers)

    soup = BeautifulSoup(response.text, "html.parser")
    results = soup.find_all("div", class_="result_overlay")

    video_links = []
    thumbnail_links = []

    for result in results:
        img_tag = result.find("img")
        if img_tag and img_tag.get("src", "").endswith(".jpg"):
            thumbnail_links.append(img_tag["src"])
        inputs = result.find_all("input", {"name": "url"})
        for inp in inputs:
            if inp.get("value", "").endswith(".mp4"):
                video_links.append(inp["value"])

    if not video_links:
        raise Exception("No video links found in savetumblr response")

    return {
        "title": "",
        "thumbnail": thumbnail_links[0] if thumbnail_links else "",
        "videos": [{"quality": "720p", "url": video_links[0], "filesize": ""}],
    }


async def download_tumblr_core(url: str):
    """
    Core Tumblr download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Tumblr video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        loop = asyncio.get_event_loop()
        task_tumblr2 = loop.run_in_executor(None, fetch_tumblr2, url)
        task_savetumblr = loop.run_in_executor(None, fetch_savetumblr, url)

        done, pending = await asyncio.wait(
            [task_tumblr2, task_savetumblr], return_when=asyncio.FIRST_COMPLETED
        )

        first_result = None
        for task in done:
            first_result = task.result()
            break

        for task in pending:
            task.cancel()

        if first_result:
            return first_result
        else:
            raise HTTPException(
                status_code=500, detail="Both Tumblr download methods failed"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tumblr download error: {str(e)}")


@tumblr_router.get("/tumblr/")
async def download_tumblr_combined(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Tumblr video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_tumblr_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
