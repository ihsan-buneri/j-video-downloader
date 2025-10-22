from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import asyncio
from bs4 import BeautifulSoup
import aiohttp


from ...auth.auth import verify_api_key

instagram_router = APIRouter(
    prefix="/download",
    tags=["Downloads"],
)


async def fetch_from_on4t(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Get CSRF token
            async with session.get(
                "https://on4t.com/instagram-video-downloader", headers=headers
            ) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                token_element = soup.find("meta", {"name": "csrf-token"})
                if not token_element:
                    raise Exception("CSRF token not found")
                token = token_element["content"]

            # Step 2: Submit download request
            payload = {"_token": token, "link[]": url}

            async with session.post(
                "https://on4t.com/all-video-download", data=payload, headers=headers
            ) as resp:
                data = await resp.json()

            if "result" not in data or not data["result"]:
                raise Exception("No result data from on4t.com")

            result = data["result"][0]

            return {
                "title": result.get("title", "Instagram Video"),
                "thumbnail": result.get("videoimg_file_url", ""),
                "videos": [
                    {
                        "quality": "1080p",
                        "url": result.get("video_file_url", ""),
                        "filesize": "null",
                    }
                ],
            }
    except Exception as e:
        raise Exception(f"on4t.com method failed: {str(e)}")


async def fetch_from_snapins(url: str):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with aiohttp.ClientSession() as session:
            # Set cookies
            await session.get("https://snapins.ai/", headers=headers)

            # Send POST request
            payload = {"url": url}

            async with session.post(
                "https://snapins.ai/action.php", data=payload, headers=headers
            ) as resp:
                data = await resp.json()

            if "data" not in data or not data["data"]:
                raise Exception("No data from snapins.ai")

            item = data["data"][0]

            # Generate title from available data since API doesn't return title
            title = item.get("title", "")
            if not title:
                import time

                author_obj = item.get("author", {})
                page_name = (
                    author_obj.get("name", "") if isinstance(author_obj, dict) else ""
                )
                author_name = (
                    author_obj.get("username", "")
                    if isinstance(author_obj, dict)
                    else ""
                )

                timestamp = int(time.time())

                if author_name:
                    title = f"{author_name} - {timestamp}"
                elif page_name:
                    title = f"{page_name} - {timestamp}"
                else:
                    title = f"Instagram Video - {timestamp}"

            return {
                "title": title,
                "thumbnail": item.get("thumbnail", ""),
                "videos": [
                    {
                        "quality": "1080p",
                        "url": item.get("videoUrl", ""),
                        "filesize": "null",
                    }
                ],
            }
    except Exception as e:
        raise Exception(f"snapins.ai method failed: {str(e)}")


async def download_instagram_core(url: str):
    """
    Core Instagram download logic without FastAPI dependencies.
    Can be used as part of another API or service.

    Args:
        url (str): Instagram video URL

    Returns:
        dict: Dictionary containing title, thumbnail, and videos array

    Raises:
        HTTPException: If download fails
    """
    try:
        task1 = asyncio.create_task(fetch_from_on4t(url))
        task2 = asyncio.create_task(fetch_from_snapins(url))

        done, pending = await asyncio.wait(
            [task1, task2], return_when=asyncio.FIRST_COMPLETED
        )

        # Check the first completed task(s)
        first_success_result = None
        for completed in done:
            try:
                result = completed.result()
                if result:
                    first_success_result = result
                    break
            except Exception:
                # Ignore error here; we'll try the remaining task(s)
                pass

        if first_success_result is not None:
            # We have a valid result; cancel any remaining work
            for task in pending:
                task.cancel()
            return first_success_result

        # If the first finished task failed or returned empty, wait for the others
        if pending:
            more_done, still_pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            # Try to get a result from the newly completed task(s)
            for completed in more_done:
                try:
                    result = completed.result()
                    if result:
                        # Cancel anything else that might still be running
                        for task in still_pending:
                            task.cancel()
                        return result
                except Exception:
                    pass

            # If nothing succeeded yet, wait for all remaining tasks to finish as a last attempt
            if still_pending:
                final_done, _ = await asyncio.wait(still_pending)
                for completed in final_done:
                    try:
                        result = completed.result()
                        if result:
                            return result
                    except Exception:
                        pass

        # If we reach here, all methods failed
        raise HTTPException(
            status_code=502, detail="Both Instagram download methods failed"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Instagram download error: {str(e)}"
        )


@instagram_router.get("/instagram/")
async def download_instagram_auto(url: str, api_key: str = Depends(verify_api_key)):
    """
    FastAPI endpoint for Instagram video download.
    Uses the core download logic and wraps it in a JSONResponse.
    """
    try:
        result = await download_instagram_core(url)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
