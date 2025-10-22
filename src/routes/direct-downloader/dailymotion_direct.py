from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
import requests
import re
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key
import json

dailymotion_router_direct = APIRouter(
    prefix="/download/direct",
    tags=["Downloads"],
)


def extract_dailymotion_id(url: str) -> str:
    """
    Extracts the Dailymotion video ID from a given URL.

    Args:
        url (str): Dailymotion video URL

    Returns:
        str: Video ID

    Raises:
        HTTPException: If the video ID cannot be extracted
    """
    # Dailymotion video ID is usually after /video/ and is alphanumeric (7-8 chars)
    match = re.search(r"dailymotion\.com/video/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    # Also support short URLs like dai.ly/xxxxxxx
    match = re.search(r"dai\.ly/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    raise HTTPException(
        status_code=400,
        detail="Invalid Dailymotion URL or unable to extract video ID.",
    )


async def download_dailymotion_core(url: str):
    """
    Core dailymotion download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Dailymotion video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        video_id = extract_dailymotion_id(url)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        session = requests.Session()
        init_response = session.get(url, headers=headers)
        soup = BeautifulSoup(init_response.text, "html.parser")

        soup_response = soup.prettify()

        # Extract the script link from <link as="script" ...>
        script_link_tag = soup.find("link", attrs={"as": "document"})
        script_link = (
            script_link_tag["href"]
            if script_link_tag and script_link_tag.has_attr("href")
            else None
        )
        second_response = session.get(script_link, headers=headers)
        soup_second = BeautifulSoup(second_response.text, "html.parser")

        second_soup_response = soup_second.prettify()

        # Extract ts and v1st from window.__PLAYER_CONFIG__ in <script>
        ts = None
        v1st = None
        script_tag = soup_second.find(
            "script", string=re.compile(r"window\.__PLAYER_CONFIG__")
        )

        # print("script_tag", script_tag)
        if script_tag:
            # Extract the JS object as a string
            script_content = script_tag.string
            # Find the JSON object after the = sign
            json_match = re.search(
                r"window\.__PLAYER_CONFIG__\s*=\s*({.*?});", script_content, re.DOTALL
            )

            if json_match:
                json_str = json_match.group(1)
                player_config = json.loads(json_str)

                # Extract ts and v1st
                ts = player_config["dmInternalData"]["ts"]
                v1st = player_config["dmInternalData"]["v1st"]

                print(f"ts: {ts}")
                print(f"v1st: {v1st}")

        # Extract player id from script_link
        player_id = None
        if script_link:
            match = re.search(r"/player/([a-zA-Z0-9]+)\.html", script_link)
            if match:
                player_id = match.group(1)

        # Extract lang from <html> tag
        html_tag = soup.find("html")
        lang = html_tag.get("lang") if html_tag and html_tag.has_attr("lang") else None
        params = {
            "legacy": "true",
            "embedder": url,
            "geo": "1",
            "player-id": player_id,
            "locale": lang,
            "dmV1st": v1st,
            "dmTs": ts,
            "is_native_app": "0",
            "app": "com.dailymotion.neon",
            "client_type": "website",
            "dmViewId": "1j62pj9674a1c1e571f",
        }
        response = requests.get(
            f"https://www.dailymotion.com/player/metadata/video/{video_id}",
            params=params,
            headers=headers,
        )
        data = response.json()
        title = data.get("title")
        thumbnail = data.get("thumbnails").get("1080")
        video_url = data.get("qualities", {}).get("auto", [{}])[0].get("url")
        return {
            "title": title,
            "thumbnail": thumbnail,
            "videos": [
                {
                    "quality": "1080p",
                    "url": video_url,
                    "filesize": "null",
                }
            ],
            "data": data,
            # "soup_response": soup_response,
            # "soup_response_second": second_soup_response,
            # "player_id": player_id,
            # "lang": lang,
            # "ts": ts,
            # "v1st": v1st,
            # "script_tag": script_tag,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=e)


@dailymotion_router_direct.get("/dailymotion/")
async def download_dailymotion(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for dailymotion video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_dailymotion_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=e)


@dailymotion_router_direct.get("/dailymotion/stream/")
async def proxy_stream(m3u8_url: str):
    """
    Simple proxy - forwards m3u8 content exactly as received from Dailymotion
    """
    if not m3u8_url:
        raise HTTPException(status_code=400, detail="m3u8_url parameter is required")

    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        # Fetch the m3u8 exactly as Dailymotion serves it
        response = requests.get(m3u8_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Forward EXACTLY as received - no processing!
        return Response(
            content=response.content,
            media_type=response.headers.get(
                "content-type", "application/vnd.apple.mpegurl"
            ),
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=300",  # Optional caching
            },
        )

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch stream: {str(e)}")
