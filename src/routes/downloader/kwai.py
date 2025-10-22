from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

kwai_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_kwai_socifan(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {"endpoint": "/v1/scraper/kwai/video-downloader", "url": url}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.socifan.com/v2/fallout-api", data=payload, headers=headers
            ) as resp:
                data = await resp.json()

            video_data = data["data"]
            return {
                "title": video_data["title"],
                "thumbnail": video_data["image"],
                "videos": [
                    {
                        "quality": "1080p",
                        "url": video_data["downloadUrl"],
                        "filesize": "null",
                    }
                ],
            }
    except Exception as e:
        raise Exception(f"socifan.com method failed: {str(e)}")


async def fetch_kwai_vidburner(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://vidburner.com/kwai-video-downloader/", headers=headers
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

            videos = [
                {"quality": "1080p", "url": item["url"], "filesize": "null"}
                for item in data["medias"]
                if item.get("extension") == "mp4"
            ]

            return {
                "title": data["title"],
                "thumbnail": data["thumbnail"],
                "videos": videos,
            }
    except Exception as e:
        raise Exception(f"vidburner.com method failed: {str(e)}")


async def download_kwai_core(url: str):
    """
    Core Kwai download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Kwai video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_kwai_socifan(url))
        task2 = asyncio.create_task(fetch_kwai_vidburner(url))

        done, pending = await asyncio.wait(
            [task1, task2], return_when=asyncio.FIRST_COMPLETED
        )

        # Check for a successful result
        for task in done:
            try:
                result = task.result()
                # Cancel other pending tasks since we have a valid result
                for t in pending:
                    t.cancel()
                return result
            except Exception:
                pass  # Ignore the failed task and move on

        # If the first completed task failed, wait for others
        if pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    result = task.result()
                    return result
                except Exception:
                    pass

        raise HTTPException(
            status_code=502, detail="Both Kwai download sources failed."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kwai download error: {str(e)}")


@kwai_router.get("/kwai/")
async def download_kwai_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Kwai video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_kwai_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
