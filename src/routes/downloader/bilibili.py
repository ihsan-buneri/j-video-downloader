from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

bilibili_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def download_bilibili_core(url: str):
    """
    Core Bilibili download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Bilibili video URL

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

        session = requests.Session()

        init_response = session.get(
            "https://vidburner.com/bilibili-video-downloader/", headers=headers
        )

        init_data = init_response.text

        soup = BeautifulSoup(init_data, "html.parser")

        token = soup.find("input", {"name": "token"})["value"]
        # print(token, "token")
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
        # print(data, "data")
        title = data["title"]
        thumbnail = data["thumbnail"]
        urls = []
        for item in data["medias"]:
            if item["extension"] == "mp4":
                urls.append(
                    {"quality": item["quality"], "url": item["url"], "filesize": "null"}
                )

        return {"title": title, "thumbnail": thumbnail, "videos": urls}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Bilibili download error: {str(e)}"
        )


@bilibili_router.get("/bilibili/")
async def download_bilibili(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Bilibili video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_bilibili_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
