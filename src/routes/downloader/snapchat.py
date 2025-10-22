from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

snapchat_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_snapchat_vidburner(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://vidburner.com/snapchat-video-downloader/", headers=headers
            ) as init_resp:
                init_html = await init_resp.text()
                soup = BeautifulSoup(init_html, "html.parser")
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
            ) as post_resp:
                data = await post_resp.json()

            title = data["title"]
            thumbnail = data["thumbnail"]
            urls = []
            for item in data["medias"]:
                if item["extension"] == "mp4":
                    urls.append(
                        {"quality": "1080p", "url": item["url"], "filesize": "null"}
                    )

            return {"title": title, "thumbnail": thumbnail, "videos": urls}
    except Exception as e:
        raise Exception(f"vidburner.com method failed: {str(e)}")


async def download_snapchat_core(url: str):
    """
    Core Snapchat download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Snapchat video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_snapchat_vidburner(url))

        done, pending = await asyncio.wait([task1], return_when=asyncio.FIRST_COMPLETED)

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        # Get result from completed task
        for finished in done:
            result = finished.result()
            if result is not None:
                return result

        # If no task completed successfully
        raise HTTPException(status_code=500, detail="Snapchat download method failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Snapchat download error: {str(e)}"
        )


@snapchat_router.get("/snapchat/")
async def download_snapchat_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Snapchat video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_snapchat_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
