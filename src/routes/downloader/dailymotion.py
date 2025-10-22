from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import requests
import time

from ...auth.auth import verify_api_key
from bs4 import BeautifulSoup
from datetime import datetime


dailymotion_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def download_dailymotion_fallback(
    url: str,
):
    try:
        response = requests.post(
            "https://ssvid.net/api/ajax/search?hl=en",
            data={"query": url, "cftoken": "", "vt": "dailymotion"},
        )
        data = response.json()

        # Expecting structure with data.links.video -> { resolution: { k: "..." } }
        links = data.get("data", {}).get("links", {}).get("video", {})

        title = data.get("data", {}).get("title", {})

        thumbnail = data.get("data", {}).get("thumbnail", {})

        if not isinstance(links, dict) or not links:
            # If structure is unexpected, return the original response
            raise HTTPException(status_code=500, detail="Unexpected structure")

        # Prefer tier by format quality (e.g., hls-1080) instead of absolute largest resolution
        QUALITY_PRIORITY = {
            "hls-1080": 0,
            "hls-720": 1,
            "hls-480": 2,
            "hls-380": 3,
        }

        def infer_priority(info: dict):
            fmt = (info.get("format") or "").lower()
            for key, pr in QUALITY_PRIORITY.items():
                if key in fmt:
                    return pr
            return 999

        def parse_resolution_key(res_key: str):
            try:
                parts = res_key.lower().split("x")
                if len(parts) != 2:
                    return 0
                width = int(parts[0].strip())
                height = int(parts[1].strip())
                return width * height
            except Exception:
                return 0

        # Choose by best quality tier first, then by resolution within that tier
        selected_key = None
        selected_priority = 999
        selected_pixels = -1
        for res_key, info in links.items():
            if not isinstance(info, dict) or not info.get("k"):
                continue
            pr = infer_priority(info)
            if pr > selected_priority:
                continue
            pixels = parse_resolution_key(res_key)
            if pr < selected_priority or pixels > selected_pixels:
                selected_priority = pr
                selected_pixels = pixels
                selected_key = res_key

        if not selected_key:
            return data

        k_value = links[selected_key]["k"]

        # Call convert endpoint with form-data payload containing key "k"
        convert_response = requests.post(
            "https://ssvid.net/api/ajax/convert",
            data={"k": k_value},
        )

        # Parse first convert attempt
        try:
            convert_json = convert_response.json()
        except Exception:
            return {
                "status": "error",
                "message": "Invalid JSON from convert",
                "raw": convert_response.text,
            }

        # If already converted (small files), return immediately
        if convert_json.get("c_status") == "CONVERTED" or convert_json.get("dlink"):
            return {
                "title": title,
                "thumbnail": thumbnail,
                "videos": [
                    {
                        "quality": "1080p",
                        "url": convert_json.get("dlink"),
                        "filesize": "null",
                    }
                ],
            }

        # If converting, poll until converted or timeout
        if convert_json.get("c_status") == "CONVERTING":
            backoff_seconds = convert_json.get("e_time", 5)
            if not isinstance(backoff_seconds, (int, float)):
                backoff_seconds = 5
            backoff_seconds = max(1, min(int(backoff_seconds), 15))

            b_id = convert_json.get("b_id")
            if not b_id:
                # Cannot proceed with server's required poll identifier
                return convert_json
            # Poll up to a reasonable number of attempts
            max_attempts = 10
            for _ in range(max_attempts):
                time.sleep(backoff_seconds)

                # Prefer sending b_id if provided; try both common param keys for robustness
                payload_candidates = []
                if b_id:
                    payload_candidates.append({"b_id": b_id})
                    payload_candidates.append({"bid": b_id})

                for payload in payload_candidates:
                    resp = requests.post(
                        "https://ssvid.net/api/ajax/convert",
                        data=payload,
                    )
                    try:
                        resp_json = resp.json()
                    except Exception:
                        continue

                    if resp_json.get("c_status") == "CONVERTED" or resp_json.get(
                        "dlink"
                    ):
                        return {
                            "title": title,
                            "thumbnail": thumbnail,
                            "videos": [
                                {
                                    "quality": "1080p",
                                    "url": resp_json.get("dlink"),
                                    "filesize": "null",
                                }
                            ],
                        }
                    if resp_json.get("c_status") == "CONVERTING":
                        # Update delay and b_id if provided
                        if isinstance(resp_json.get("e_time"), (int, float)):
                            backoff_seconds = max(
                                1, min(int(resp_json.get("e_time")), 15)
                            )
                        if resp_json.get("b_id"):
                            b_id = resp_json.get("b_id")
                        # Continue outer loop to sleep again
                        break
                else:
                    # None of the payloads returned valid JSON; keep looping using last delay
                    continue

            # Fallback if not converted after attempts
            raise HTTPException(
                status_code=500, detail="Conversion still in progress after polling"
            )

        # Default: return whatever we received
        return {
            "title": title,
            "thumbnail": thumbnail,
            "videos": [
                {
                    "quality": "1080p",
                    "url": convert_json.get("dlink"),
                    "filesize": "null",
                }
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=e)


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
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        session = requests.Session()

        init_response = session.get(
            "https://on4t.com/dailymotion-video-downloader", headers=headers
        )
        init_data = init_response.text

        soup = BeautifulSoup(init_data, "html.parser")
        token = soup.find("meta", {"name": "csrf-token"})["content"]

        payload = {"_token": token, "link[]": url}

        response = session.post(
            "https://on4t.com/all-video-download", data=payload, headers=headers
        )
        data = response.json()
        title = data["result"][0].get("title", "").strip()
        if not title:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = f"title - {current_time}"
        # Handle missing thumbnail
        thumbnail = data["result"][0].get("videoimg_file_url", "")

        # Handle missing video URL
        video_url = data["result"][0].get("video_file_url", "")
        if not video_url:
            return await download_dailymotion_fallback(url)

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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=e)


@dailymotion_router.get("/dailymotion/")
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
