from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from ...auth.auth import verify_api_key

pinterest_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


def clean_pinterest_url(url: str) -> str:
    """
    Clean and normalize a Pinterest URL by removing titles or extra parameters 
    and converting it to a standard format.
    
    Args:
        url (str): Raw Pinterest URL to clean
        
    Returns:
        str: Cleaned and normalized Pinterest URL
    """
    import re
    
    # First, remove query parameters to work with clean path
    base_url = url.split('?')[0]
    
    # Pattern to match Pinterest URLs with titles in the path like:
    # https://www.pinterest.com/pin/how-to-link-you-instagram-with-your-pinterest--232779874483408878/
    # https://in.pinterest.com/pin/how-to-create-a-pinterest-board-stepbystep-guide--323907398221372312/
    # https://ca.pinterest.com/pin/no-views-on-your-pins-heres-why--286119382570850673/
    # Extract the pin ID from the end (numbers before the final slash)
    # This pattern handles:
    # - Standard: www.pinterest.com
    # - International: in.pinterest.com, ca.pinterest.com, etc.
    # - Two-part TLDs: pinterest.co.uk, pinterest.co.jp, etc.
    pin_with_title_pattern = r"(https?://(?:www\.|)(?:[a-z]{2,3}\.)?pinterest\.[a-z]{2,3}/pin/)[^/]*--(\d+)/?$"
    
    match = re.search(pin_with_title_pattern, base_url)
    if match:
        base_path = match.group(1)
        pin_id = match.group(2)
        return f"{base_path}{pin_id}/"  # Always add trailing slash for pin URLs
    
    # Handle URLs with just query parameters (no titles)
    clean_url = url.split('?')[0]
    
    # Ensure the URL has proper ending format
    if not clean_url.endswith('/'):
        # If it looks like a pin URL without a slash, add one
        if '/pin/' in clean_url or '/pin.it/' in clean_url:
            clean_url += '/'
    
    return clean_url


def validate_pinterest_url(url: str) -> bool:
    """
    Validate if the URL is a valid Pinterest URL.
    
    Args:
        url (str): Pinterest URL to validate
        
    Returns:
        bool: True if valid Pinterest URL, False otherwise
    """
    # Check if URL matches Pinterest patterns
    pinterest_patterns = [
        r"^https?://(?:www\.)?pinterest\.com(/.*)?$",                    # Standard Pinterest domain
        r"^https?://(?:www\.)?pin\.it(/.*)?$",                           # Shortened Pinterest URLs
        r"^https?://(?:www\.|)(?:[a-z]{2,3}\.)?pinterest\.[a-z]{2,3}(/.*)?$", # International domains like pinterest.fr, in.pinterest.com, ca.pinterest.com
        r"^https?://(?:www\.)?pinterest\.[a-z]{2}\.[a-z]{2}(/.*)?$",     # Two-part domains like pinterest.co.uk
    ]
    
    for pattern in pinterest_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


async def fetch_from_savepin_v2(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}

    lang = "en"
    type_ = "redirect"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.savepin.app/download.php?url={url}&lang={lang}&type={type_}",
                headers=headers,
            ) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        thumbnail = soup.find("div", class_="image-container").find("img")["src"]
        title = soup.find("div", class_="table-container").find("h1").text
        video_url = soup.find("a", class_="button is-success is-small")["href"]
        video_url = (
            video_url.replace("force-save.php?url=", "")
            .replace("%3A", ":")
            .replace("%2F", "/")
        )

        return {
            "title": title,
            "thumbnail": thumbnail,
            "videos": [{"quality": "1080p", "url": video_url, "filesize": "null"}],
        }
    except Exception as e:
        raise Exception(f"savepin.app method failed: {str(e)}")


async def fetch_from_savepin_with_fdown(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}

    lang = "en"
    type_ = "redirect"

    try:
        async with aiohttp.ClientSession() as session:
            # Dummy call to fdown.net to simulate cookie handling
            await session.get("https://www.fdown.net", headers=headers)

            async with session.get(
                f"https://www.savepin.app/download.php?url={url}&lang={lang}&type={type_}",
                headers=headers,
            ) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        thumbnail = soup.find("div", class_="image-container").find("img")["src"]
        title = soup.find("div", class_="table-container").find("h1").text
        video_url = soup.find("a", class_="button is-success is-small")["href"]
        video_url = (
            video_url.replace("force-save.php?url=", "")
            .replace("%3A", ":")
            .replace("%2F", "/")
        )

        return {
            "title": title,
            "thumbnail": thumbnail,
            "videos": [{"quality": "1080p", "url": video_url, "filesize": "null"}],
        }
    except Exception as e:
        raise Exception(f"savepin.app with fdown method failed: {str(e)}")


async def download_pinterest_core(url: str):
    """
    Core Pinterest download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Pinterest video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    # Clean the URL first
    cleaned_url = clean_pinterest_url(url)
    
    # Validate the cleaned URL
    if not validate_pinterest_url(cleaned_url):
        raise HTTPException(
            status_code=400, 
            detail="Invalid Pinterest URL. Please provide a valid Pinterest video URL from pinterest.com or pin.it"
        )
    
    try:
        task1 = asyncio.create_task(fetch_from_savepin_v2(cleaned_url))
        task2 = asyncio.create_task(fetch_from_savepin_with_fdown(cleaned_url))

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
            status_code=500, detail="Both Pinterest download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Pinterest download error: {str(e)}"
        )


@pinterest_router.get("/pinterest/")
async def download_pinterest_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Pinterest video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    # Clean the URL first
    cleaned_url = clean_pinterest_url(url)
    
    # Validate the cleaned URL
    if not validate_pinterest_url(cleaned_url):
        raise HTTPException(
            status_code=400, 
            detail="Invalid Pinterest URL. Please provide a valid Pinterest video URL from pinterest.com or pin.it"
        )
    
    try:
        result = await download_pinterest_core(cleaned_url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
