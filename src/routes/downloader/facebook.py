from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

facebook_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_from_getsave(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }
    print(url, "url from getsave")
    try:
        resp = requests.post(
            "https://getsave.net/proxy.php",
            data={"url": url},
            headers=headers,
            timeout=30,
        )
        data = resp.json()
        print(data, "data from getsave")
        title = data["api"]["title"]
        thumbnail_url = data["api"]["mediaItems"][0].get("mediaThumbnail")

        videos = []
        for item in data["api"]["mediaItems"]:
            if item.get("type") == "Video":
                try:
                    quality = item.get("mediaQuality")
                    file_size = item.get("mediaFileSize")
                    file_resp = requests.get(item.get("mediaUrl"), headers=headers)
                    file_data = file_resp.json()
                    videos.append(
                        {
                            "quality": quality,
                            "url": file_data["fileUrl"],
                            "filesize": file_size,
                        }
                    )
                except Exception:
                    continue

        return {"title": title, "thumbnail": thumbnail_url, "videos": videos}

    except Exception as e:
        raise Exception(f"getsave.net method failed: {str(e)}")


async def fetch_from_saveas(url: str):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        print(url, "url from saveas")
        resp = requests.post(
            "https://saveas.co/smart_download.php",
            data={"fb_url": url},
            headers=headers,
            timeout=30,
        )
        data = resp.text

        print(data, "data from saveas")
        soup = BeautifulSoup(data, "html.parser")

        img_element = soup.select_one("img")
        thumbnail_url = img_element.get("src") if img_element else None
        title_element = soup.select_one("div.info h2")
        title = title_element.text.strip() if title_element else "Unknown Title"

        description_element = soup.find(text=lambda x: x and "Description:" in x)
        description = (
            description_element.parent.get_text().replace("Description:", "").strip()
            if description_element
            else "No description available"
        )

        duration_element = soup.find(text=lambda x: x and "Duration:" in x)
        duration = (
            duration_element.parent.get_text().replace("Duration:", "").strip()
            if duration_element
            else "Unknown duration"
        )
        sd_element = soup.select_one("#sdLink")
        hd_element = soup.select_one("#hdLink")
        sd_link = sd_element.get("href") if sd_element else None
        hd_link = hd_element.get("href") if hd_element else None

        return {
            "title": title,
            "thumbnail": thumbnail_url,
            "description": description,
            "duration": duration,
            "videos": [
                {"quality": "SD", "url": sd_link, "filesize": "null"},
                {"quality": "HD", "url": hd_link, "filesize": "null"},
            ],
        }
    except Exception as e:
        raise Exception(f"saveas.co method failed: {str(e)}")


async def download_facebook_core(url: str):
    """
    Core Facebook download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Facebook video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        print(url, "url from facebook download core")
        # Primary: try saveas.co first
        try:
            primary_result = await fetch_from_saveas(url)
            if primary_result:
                return primary_result
        except Exception:
            pass

        # Fallback: try getsave.net if primary failed
        try:
            fallback_result = await fetch_from_getsave(url)
            if fallback_result:
                return fallback_result
        except Exception:
            pass

        # If we reach here, both methods failed
        raise HTTPException(
            status_code=502, detail="Both Facebook download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Facebook download error: {str(e)}"
        )


@facebook_router.get("/facebook/")
async def download_facebook_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Facebook video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_facebook_core(url)
        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
