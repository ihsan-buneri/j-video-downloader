from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

linkedin_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_linkedin_vidburner(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://vidburner.com/linkedin-video-downloader/", headers=headers
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
                {"quality": "1080p", "url": item["url"], "filesize": "null"}
                for item in data["medias"]
                if item.get("extension") == "mp4"
            ]

            return {
                "title": data["title"],
                "thumbnail": data["thumbnail"],
                "videos": urls,
            }
    except Exception as e:
        raise Exception(f"vidburner.com method failed: {str(e)}")


async def fetch_linkedin_ez4cast(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {"url": url}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://us-central1-ez4cast.cloudfunctions.net/tweetVideoURL-getLinkedinVideoURL",
                data=payload,
                headers=headers,
            ) as resp:
                data = await resp.json()

            return {
                "title": "",
                "thumbnail": "",
                "videos": [
                    {"quality": "1080p", "url": data["src"], "filesize": "null"}
                ],
            }
    except Exception as e:
        raise Exception(f"ez4cast method failed: {str(e)}")


async def download_linkedin_core(url: str):
    """
    Core LinkedIn download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): LinkedIn video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_linkedin_vidburner(url))
        task2 = asyncio.create_task(fetch_linkedin_ez4cast(url))

        done, pending = await asyncio.wait(
            [task1, task2], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Get result from completed task
        for finished in done:
            result = finished.result()
            if result:
                return result

        # If no task completed successfully
        raise HTTPException(
            status_code=500, detail="Both LinkedIn download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"LinkedIn download error: {str(e)}"
        )


@linkedin_router.get("/linkedin/")
async def download_linkedin_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for LinkedIn video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_linkedin_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
