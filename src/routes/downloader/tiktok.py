from fastapi import APIRouter, HTTPException, Depends
import requests
import re
import json
import base64
from typing import Dict, Any
from ...auth.auth import verify_api_key
from bs4 import BeautifulSoup

tiktok_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


def extract_savetik_data(html_content: str) -> Dict[str, Any]:
    """
    Extract video data from savetik.co HTML response
    """
    extracted = {}

    # Extract title from h3 tag
    title_pattern = r"<h3>([^<]+)</h3>"
    title_match = re.search(title_pattern, html_content)
    if title_match:
        extracted["title"] = title_match.group(1).strip()

    # Extract thumbnail URL
    thumbnail_pattern = r'<img src="([^"]+)"'
    thumbnail_match = re.search(thumbnail_pattern, html_content)
    if thumbnail_match:
        extracted["thumbnail"] = thumbnail_match.group(1)

    # Extract video URLs from download links
    download_patterns = [
        r'href="(https://dl\.snapcdn\.app/get\?token=[^"]+)"',  # JWT token URLs
        r'data-src="([^"]+)"',  # Video data-src attribute
    ]

    video_urls = []
    for pattern in download_patterns:
        matches = re.findall(pattern, html_content)
        video_urls.extend(matches)

    if video_urls:
        extracted["video_urls"] = list(set(video_urls))

    # Extract TikTok video ID from hidden input
    id_pattern = r'<input type="hidden" id="TikTokId" value="(\d+)"'
    id_match = re.search(id_pattern, html_content)
    if id_match:
        extracted["video_id"] = id_match.group(1)

    # Extract JWT tokens for potential decoding
    jwt_pattern = r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    jwt_tokens = re.findall(jwt_pattern, html_content)
    if jwt_tokens:
        extracted["jwt_tokens"] = jwt_tokens

        # Try to decode JWT payloads
        decoded_payloads = []
        for token in jwt_tokens:
            try:
                parts = token.split(".")
                if len(parts) >= 2:
                    payload = parts[1]
                    # Add padding if needed
                    payload += "=" * (4 - len(payload) % 4)
                    decoded = base64.b64decode(payload)
                    payload_json = json.loads(decoded.decode("utf-8"))
                    decoded_payloads.append(payload_json)
            except Exception:
                continue

        if decoded_payloads:
            extracted["decoded_jwt_data"] = decoded_payloads

    return extracted


async def download_tiktok_savetik(url: str):
    """
    TikTok download endpoint using savetik.co API
    """
    try:
        payload = {"q": url, "lang": "en2", "cftoken": ""}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        response = requests.post(
            "https://savetik.co/api/ajaxSearch", data=payload, headers=headers
        )

        response_data = response.json()

        if response_data.get("status") != "ok":
            raise HTTPException(status_code=400, detail="API returned error status")

        html_content = response_data.get("data", "")
        if not html_content:
            raise HTTPException(status_code=400, detail="No data received from API")

        # Extract data from HTML
        extracted_data = extract_savetik_data(html_content)

        # Create simplified response with priority-based video URL selection
        result = {
            "title": extracted_data.get("title", ""),
            "thumbnail": extracted_data.get("thumbnail", ""),
            "video_url": "",
        }

        # Priority-based video URL selection
        video_urls = extracted_data.get("video_urls", [])

        # 1. First priority: MP4 standard quality (not TikTok direct URLs)
        if not result["video_url"]:
            for url in video_urls:
                if (
                    url.endswith(".mp4") or "mp4" in url.lower()
                ) and "tiktokcdn.com" not in url:
                    result["video_url"] = url
                    break

        # 2. Second priority: HD quality from JWT data
        if (
            not result["video_url"]
            and "decoded_jwt_data" in extracted_data
            and extracted_data["decoded_jwt_data"]
        ):
            for jwt_data in extracted_data["decoded_jwt_data"]:
                if "url" in jwt_data and "hd" in jwt_data.get("filename", "").lower():
                    result["video_url"] = jwt_data["url"]
                    break

        # 3. Third priority: HD quality from video URLs (look for HD indicators)
        if not result["video_url"]:
            for url in video_urls:
                if any(
                    indicator in url.lower() for indicator in ["hd", "original", "high"]
                ):
                    result["video_url"] = url
                    break

        # 4. Fourth priority: Any MP4 URL (including TikTok direct)
        if not result["video_url"]:
            for url in video_urls:
                if url.endswith(".mp4") or "mp4" in url.lower():
                    result["video_url"] = url
                    break

        # 5. Last priority: Any TikTok direct URL
        if not result["video_url"]:
            for url in video_urls:
                if "tiktokcdn.com" in url:
                    result["video_url"] = url
                    break

        # 6. Fallback: First available URL
        if not result["video_url"] and video_urls:
            result["video_url"] = video_urls[0]

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def download_tiktok_core(url: str):
    """
    Core TikTok download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): TikTok video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        # Primary method: ssstik.io
        payload = {"id": url, "locale": "en", "tt": "bkJ0RTI2"}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        response = requests.post(
            "https://ssstik.io/abc?url=dl", data=payload, headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"ssstik.io returned status {response.status_code}")

        data = response.text
        soup = BeautifulSoup(data, "html.parser")

        # Try to extract data from ssstik.io
        title_element = soup.find("p", class_="maintext")
        thumbnail_element = soup.find("img", class_="result_author")
        video_element = soup.find(
            "a",
            class_="pure-button pure-button-primary is-center u-bl dl-button download_link without_watermark vignette_active notranslate",
        )

        if title_element and thumbnail_element and video_element:
            title = title_element.text.strip()
            thumbnail = thumbnail_element.get("src", "")
            video_url = video_element.get("href", "")

            if video_url:
                return {
                    "title": title,
                    "thumbnail": thumbnail,
                    "videos": [
                        {"quality": "1080p", "url": video_url, "filesize": "null"}
                    ],
                }

        # Fallback to savetik.co
        result = await download_tiktok_savetik(url)
        return {
            "title": result["title"],
            "thumbnail": result["thumbnail"],
            "videos": [
                {"quality": "1080p", "url": result["video_url"], "filesize": "null"}
            ],
        }

    except Exception as e:
        try:
            # Final fallback to savetik.co
            result = await download_tiktok_savetik(url)
            return {
                "title": result["title"],
                "thumbnail": result["thumbnail"],
                "videos": [
                    {"quality": "1080p", "url": result["video_url"], "filesize": "null"}
                ],
            }
        except Exception as fallback_error:
            raise HTTPException(
                status_code=500,
                detail=f"Both methods failed. Primary: {str(e)}, Fallback: {str(fallback_error)}",
            )


@tiktok_router.get("/tiktok/")
async def download_tiktok(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for TikTok video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_tiktok_core(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
