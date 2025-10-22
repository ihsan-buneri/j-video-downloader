from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

rumble_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def download_rumble_core(url: str):
    """
    Core Rumble download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Rumble video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        payload = {
            "video_url": url,
        }

        session = requests.Session()
        response = session.post(
            "https://orbitdownloader.com/rumble-video-downloader/submit",
            headers=headers,
            data=payload,
        )

        data = response.text

        soup = BeautifulSoup(data, "html.parser")

        title = soup.find("div", class_="preview-header").find("h1").text

        thumbnail = soup.find("div", class_="thumbnail-container").find("img")["src"]

        urls = []
        for item in soup.find_all("div", class_="format-card"):
            quality = item.find("span", class_="resolution-label").text
            url = item.find("a", class_="download-button")["href"]
            urls.append({"quality": quality, "url": url, "filesize": "null"})

        return {"title": title, "thumbnail": thumbnail, "videos": urls}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rumble download error: {str(e)}")


@rumble_router.get("/rumble/")
async def download_rumble(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Rumble video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_rumble_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
