from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

imdb_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_imdb_vidburner(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://vidburner.com/imdb-video-downloader/", headers=headers
            ) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                token = soup.find("input", {"name": "token"})["value"]

            payload = {
                "url": url,
                "token": token,
                "hash": "aHR0cHM6Ly93d3cuYmlsaWJpbGkuY29tL3ZpZGVvL0JWMWNzNzl6bUVDby8=1044YWlvLWRs",
            }

            async with session.post(
                "https://vidburner.com/wp-json/aio-dl/video-data/",
                data=payload,
                headers=headers,
            ) as resp:
                data = await resp.json()

            urls = [
                {
                    "quality": "1080p",
                    "url": data["medias"][-1]["url"],
                    "filesize": "null",
                }
            ]

            return {
                "title": data["title"],
                "thumbnail": data["thumbnail"],
                "videos": urls,
            }
    except Exception as e:
        raise Exception(f"vidburner.com method failed: {str(e)}")


async def download_imdb_core(url: str):
    """
    Core IMDb download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): IMDb video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task2 = asyncio.create_task(fetch_imdb_vidburner(url))

        done, pending = await asyncio.wait([task2], return_when=asyncio.FIRST_COMPLETED)

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Get result from completed task
        for completed in done:
            result = completed.result()
            if result:
                return result

        # If no task completed successfully
        raise HTTPException(status_code=500, detail="IMDb download method failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"IMDb download error: {str(e)}")


@imdb_router.get("/imdb/")
async def download_imdb_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for IMDb video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_imdb_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
