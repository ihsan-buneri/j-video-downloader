# from fastapi import APIRouter, HTTPException
# from bs4 import BeautifulSoup
# import requests
# import re
# from typing import Dict, Any, Optional

# instagram_scrape = APIRouter(prefix="/v2", tags=["instagram"])


# def validate_instagram_url(url: str) -> bool:
#     """Validate if the URL is a valid Instagram post URL"""
#     patterns = [
#         r"^https?://(www\.)?instagram\.com/p/[^/]+/?",
#         r"^https?://(www\.)?instagram\.com/reel/[^/]+/?",
#         r"^https?://(www\.)?instagram\.com/stories/[^/]+/\d+/?",
#     ]
#     return any(re.match(pattern, url) for pattern in patterns)


# def _get_meta_content(
#     soup: BeautifulSoup, key: str, attr: str = "property"
# ) -> Optional[str]:
#     tag = soup.find("meta", {attr: key})
#     return tag.get("content") if tag and tag.has_attr("content") else None


# def _extract_username_from_twitter_title(title: str) -> Optional[str]:
#     match = re.search(r"\(@([^)]+)\)", title)
#     return match.group(1) if match else None


# def _extract_username_from_url(url: str) -> Optional[str]:
#     match = re.search(r"instagram\.com/([^/]+)/", url)
#     return match.group(1) if match else None


# def _generate_short_title(base_title: Optional[str], username: Optional[str]) -> str:
#     # Prefer quoted caption if present
#     caption = ""
#     if base_title:
#         m = re.search(r'"([^"]+)"', base_title)
#         if m:
#             caption = m.group(1)
#         else:
#             if " on Instagram:" in base_title:
#                 caption = base_title.split(" on Instagram:", 1)[-1]
#             elif ":" in base_title:
#                 caption = base_title.split(":", 1)[-1]
#             else:
#                 caption = base_title

#     caption = caption.strip()

#     if not caption and username:
#         return f"@{username}"

#     # Remove URLs and bullets
#     caption = re.sub(r"https?://\S+", " ", caption)
#     caption = caption.replace("•", " ")

#     # Remove punctuation/emojis except spaces and word chars
#     caption = re.sub(r"[^\w\s]", " ", caption, flags=re.UNICODE)

#     # Split and take first 4 words
#     words = [w for w in re.split(r"\s+", caption) if w]
#     if not words:
#         return f"@{username}" if username else "Instagram Video"

#     short = " ".join(words[:4])
#     return short


# def parse_instagram_soup(soup: BeautifulSoup, page_url: str) -> Dict[str, Any]:
#     og_video = _get_meta_content(soup, "og:video") or _get_meta_content(
#         soup, "og:video:secure_url"
#     )
#     og_image = _get_meta_content(soup, "og:image")
#     og_title = _get_meta_content(soup, "og:title")
#     twitter_title = _get_meta_content(soup, "twitter:title", attr="name")
#     og_url = _get_meta_content(soup, "og:url") or page_url

#     media_type = "video" if og_video else "image"
#     download_url = og_video if media_type == "video" else og_image
#     thumbnail_url = og_image

#     base_title = og_title or twitter_title
#     username = _extract_username_from_twitter_title(
#         twitter_title or ""
#     ) or _extract_username_from_url(og_url)

#     title = _generate_short_title(base_title, username)

#     return {
#         "data": {
#             "title": title,
#             "thumbnail": thumbnail_url,
#             "videos": [
#                 {
#                     "quality": "1080p",
#                     "url": download_url,
#                     "filesize": "null",
#                 }
#             ],
#         },
#         "download_url": download_url,
#     }


# async def download_instagram_direct(url: str) -> Dict[str, Any]:
#     if not validate_instagram_url(url):
#         raise HTTPException(status_code=400, detail="Invalid Instagram URL")

#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
#         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#         "Accept-Language": "en-US,en;q=0.5",
#         "Accept-Encoding": "gzip, deflate",
#         "Connection": "keep-alive",
#         "Upgrade-Insecure-Requests": "1",
#         "Sec-Fetch-Dest": "document",
#         "Sec-Fetch-Mode": "navigate",
#         "Sec-Fetch-Site": "none",
#         "Sec-Fetch-User": "?1",
#     }

#     try:
#         resp = requests.get(url, headers=headers, timeout=30)
#         resp.raise_for_status()
#         soup = BeautifulSoup(resp.text, "html.parser")
#         parsed = parse_instagram_soup(soup, resp.url)

#         if not parsed.get("download_url"):
#             raise HTTPException(status_code=404, detail="No downloadable media found")

#         return parsed.get("data")
#     except requests.RequestException as e:
#         raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
