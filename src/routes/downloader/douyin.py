from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

douyin_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_douyin_savedouyin(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {"url": url}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://savedouyin.net/proxy.php", data=payload, headers=headers
            ) as resp:
                data = await resp.json()

            title = data["api"]["title"]
            thumbnail = data["api"]["imagePreviewUrl"]

            urls = []
            for item in data["api"]["mediaItems"]:
                if item["type"] == "Video":
                    # Follow redirect to get final media file
                    async with session.get(
                        item["mediaUrl"], headers=headers
                    ) as media_resp:
                        media_data = await media_resp.json()
                        urls.append(
                            {
                                "quality": item["mediaRes"],
                                "url": media_data["fileUrl"],
                                "filesize": "null",
                            }
                        )

            return {"title": title, "thumbnail": thumbnail, "videos": urls}
    except Exception as e:
        raise Exception(f"savedouyin.net method failed: {str(e)}")


async def fetch_douyin_vidburner(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Get token
            async with session.get(
                "https://vidburner.com/douyin-video-downloader/", headers=headers
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
                "title": data.get("title", ""),
                "thumbnail": data.get("thumbnail", ""),
                "videos": urls,
            }
    except Exception as e:
        raise Exception(f"vidburner.com method failed: {str(e)}")


async def download_douyin_core(url: str):
    """
    Core Douyin download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Douyin video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_douyin_savedouyin(url))
        task2 = asyncio.create_task(fetch_douyin_vidburner(url))

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
            status_code=500, detail="Both Douyin download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Douyin download error: {str(e)}")


@douyin_router.get("/douyin/")
async def download_douyin_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Douyin video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_douyin_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
