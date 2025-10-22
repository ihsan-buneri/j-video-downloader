from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

bitchute_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_bitchute_toolsed(url: str):
    api_url = f"https://save.toolsed.com/wp-json/aio-dl/api/?url={url}&key=a0fe74727df4e68aed7abf10678920b3ec947a25341b12a43e157b5a03fbfa5b"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                data = await resp.json()

        return {
            "title": data["title"],
            "thumbnail": data["thumbnail"],
            "videos": [
                {
                    "quality": "1080p",
                    "url": data["medias"][0]["url"],
                    "filesize": "null",
                }
            ],
        }
    except Exception as e:
        raise Exception(f"toolsed.com method failed: {str(e)}")


async def fetch_bitchute_vidburner(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Get token
            async with session.get(
                "https://vidburner.com/bitchute-video-downloader/", headers=headers
            ) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                token = soup.find("input", {"name": "token"})["value"]

            # Replace hardcoded URL with input URL
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
            {"quality": "1080p", "url": item["url"], "filesize": "null"}
            for item in data["medias"]
            if item.get("extension") == "mp4"
        ]

        return {"title": data["title"], "thumbnail": data["thumbnail"], "videos": urls}
    except Exception as e:
        raise Exception(f"vidburner.com method failed: {str(e)}")


async def download_bitchute_core(url: str):
    """
    Core BitChute download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): BitChute video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_bitchute_toolsed(url))
        task2 = asyncio.create_task(fetch_bitchute_vidburner(url))

        done, pending = await asyncio.wait(
            [task1, task2], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Get result from completed task
        for completed in done:
            result = completed.result()
            if result:
                return result

        # If no task completed successfully
        raise HTTPException(
            status_code=500, detail="Both BitChute download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"BitChute download error: {str(e)}"
        )


@bitchute_router.get("/bitchute/")
async def download_bitchute_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for BitChute video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_bitchute_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
