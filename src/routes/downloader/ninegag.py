from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

ninegag_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_9gag_steptodown(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Get token
            async with session.get(
                "https://steptodown.com/9gag-video-downloader/", headers=headers
            ) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                token = soup.find("input", {"name": "token"})["value"]

            # Step 2: Post to fetch data
            payload = {"url": url, "token": token}

            async with session.post(
                "https://steptodown.com/wp-json/aio-dl/video-data/",
                data=payload,
                headers=headers,
            ) as resp:
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
        raise Exception(f"steptodown.com method failed: {str(e)}")


async def fetch_9gag_storyclone(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            api_url = f"https://storyclone.com/api/fetchMedia?url={url}"
            async with session.get(api_url, headers=headers) as resp:
                data = await resp.json()

            return {
                "title": data["title"],
                "thumbnail": data["thumbnail"],
                "videos": [
                    {
                        "quality": data["medias"][0]["quality"],
                        "url": data["medias"][0]["url"],
                        "filesize": "",
                    }
                ],
            }
    except Exception as e:
        raise Exception(f"storyclone.com method failed: {str(e)}")


async def download_9gag_core(url: str):
    """
    Core 9GAG download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): 9GAG video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_9gag_steptodown(url))
        task2 = asyncio.create_task(fetch_9gag_storyclone(url))

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
        raise HTTPException(status_code=500, detail="Both 9GAG download methods failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"9GAG download error: {str(e)}")


@ninegag_router.get("/9gag/")
async def download_9gag_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for 9GAG video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_9gag_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
