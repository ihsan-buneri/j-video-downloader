from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import requests
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key
from typing import Dict

buzzfeed_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


def fetch_steptodown(url: str) -> Dict:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    init_response = session.get(
        "https://steptodown.com/buzzfeed-video-downloader/", headers=headers
    )
    soup = BeautifulSoup(init_response.text, "html.parser")
    token = soup.find("input", {"name": "token"})["value"]

    payload = {
        "url": url,
        "token": token,
    }
    response = session.post(
        "https://steptodown.com/wp-json/aio-dl/video-data/",
        data=payload,
        headers=headers,
    )
    data = response.json()
    # print(data, "data from steptodown")
    title = data["title"]
    thumbnail = data["thumbnail"]
    urls = [
        {
            "quality": data["medias"][0]["quality"],
            "url": data["medias"][0]["url"],
            "filesize": data["medias"][0].get("formattedSize", "null"),
        }
    ]

    return {"title": title, "thumbnail": thumbnail, "videos": urls}


def fetch_vidburner(url: str) -> Dict:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    session = requests.Session()
    init_response = session.get(
        "https://vidburner.com/buzzfeed-video-downloader/", headers=headers
    )
    soup = BeautifulSoup(init_response.text, "html.parser")
    token = soup.find("input", {"name": "token"})["value"]

    payload = {
        "url": url,
        "token": token,
        "hash": "aHR0cHM6Ly93d3cuYmlsaWJpbGkuY29tL3ZpZGVvL0JWMWNzNzl6bUVDby8=1044YWlvLWRs",
    }
    response = session.post(
        "https://vidburner.com/wp-json/aio-dl/video-data/",
        data=payload,
        headers=headers,
    )
    data = response.json()
    # print(data, "data from vidburner")
    title = data["title"]
    thumbnail = data["thumbnail"]
    urls = []
    for item in data["medias"]:
        if item["extension"] == "mp4":
            urls.append(
                {"quality": item["quality"], "url": item["url"], "filesize": "null"}
            )

    return {"title": title, "thumbnail": thumbnail, "videos": urls}


async def download_buzzfeed_core(url: str):
    """
    Core Buzzfeed download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Buzzfeed video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        loop = asyncio.get_event_loop()
        # Run both in thread pool executor concurrently
        task_steptodown = loop.run_in_executor(None, fetch_steptodown, url)
        task_vidburner = loop.run_in_executor(None, fetch_vidburner, url)

        done, pending = await asyncio.wait(
            [task_steptodown, task_vidburner], return_when=asyncio.FIRST_COMPLETED
        )

        # Try to get a successful result from the first completed task
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
                # Wait for the remaining tasks
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
                detail=f"Buzzfeed download failed: {str(first_error) if first_error else 'Unknown error'}",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Buzzfeed download error: {str(e)}"
        )


@buzzfeed_router.get("/buzzfeed/")
async def download_buzzfeed_combined(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Buzzfeed video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_buzzfeed_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
