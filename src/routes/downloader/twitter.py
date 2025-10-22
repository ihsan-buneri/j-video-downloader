from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

twitter_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_from_xdown1(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with aiohttp.ClientSession() as session:
            await session.get("https://xdown.app/en", headers=headers)

            payload = {"q": url, "lang": "en"}

            async with session.post(
                "https://xdown.app/api/ajaxSearch", data=payload, headers=headers
            ) as resp:
                data = await resp.json()

        soup = BeautifulSoup(data["data"], "html.parser")

        thumbnail = soup.find("div", class_="image-tw open-popup").find("img")["src"]
        title = soup.find("div", class_="clearfix").find("h3").text
        video_url = soup.find("a", class_="tw-button-dl button dl-success")["href"]

        return {
            "title": title,
            "thumbnail": thumbnail,
            "videos": [{"quality": "1280p", "url": video_url, "filesize": "null"}],
        }
    except Exception as e:
        raise Exception(f"xdown.app method 1 failed: {str(e)}")


async def fetch_from_xdown2(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        payload = {"q": url, "lang": "en", "cftoken": ""}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://xdown.app/api/ajaxSearch", data=payload, headers=headers
            ) as resp:
                data = await resp.json()

        soup = BeautifulSoup(data["data"], "html.parser")

        thumbnail = soup.find("div", class_="image-tw open-popup").find("img")["src"]
        title = soup.find("div", class_="clearfix").find("h3").text
        video_url = soup.find("a", class_="tw-button-dl button dl-success")["href"]

        return {
            "title": title,
            "thumbnail": thumbnail,
            "videos": [{"quality": "720p", "url": video_url, "filesize": "null"}],
        }
    except Exception as e:
        raise Exception(f"xdown.app method 2 failed: {str(e)}")


async def download_twitter_core(url: str):
    """
    Core Twitter/X download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Twitter/X video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_from_xdown1(url))
        task2 = asyncio.create_task(fetch_from_xdown2(url))

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
            status_code=500, detail="Both Twitter/X download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Twitter/X download error: {str(e)}"
        )


@twitter_router.get("/x/")
async def download_twitter_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Twitter/X video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_twitter_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
