# import asyncio
# import time
# import re
# import requests
# import os
# from datetime import datetime
# from PIL import Image
# import imageio
# from bs4 import BeautifulSoup
# from selenium import webdriver
# from selenium.webdriver.firefox.service import Service
# from selenium.webdriver.firefox.options import Options
# from webdriver_manager.firefox import GeckoDriverManager
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC


# def generate_video_thumbnail_pil(video_path: str, title: str) -> str:
#     """Generate a thumbnail from video using PIL + imageio."""
#     try:
#         thumbnails_dir = "public/thumbnails"
#         os.makedirs(thumbnails_dir, exist_ok=True)

#         safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         thumbnail_filename = f"{safe_title}_{timestamp}.webp"
#         thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)

#         print(f"🖼️ Generating thumbnail: {video_path}")

#         video = imageio.get_reader(video_path)
#         try:
#             frame = video.get_data(30)  # ~1s mark
#         except Exception:
#             frame = video.get_data(0)
#         img = Image.fromarray(frame)
#         img.thumbnail((640, 480), Image.Resampling.LANCZOS)

#         final_img = Image.new("RGB", (640, 480), (0, 0, 0))
#         final_img.paste(img, ((640 - img.width) // 2, (480 - img.height) // 2))
#         final_img.save(thumbnail_path, "WEBP", quality=85, optimize=True)

#         video.close()
#         return f"/public/thumbnails/{thumbnail_filename}"
#     except Exception as e:
#         print(f"❌ Thumbnail error: {e}")
#         return None


# def download_video_file(video_url: str, title: str, cookies: dict = None):
#     """Download TikTok video with cookies + generate thumbnail."""
#     try:
#         public_dir = "public/videos"
#         os.makedirs(public_dir, exist_ok=True)

#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
#         filename = f"{safe_title}_{timestamp}.mp4"
#         file_path = os.path.join(public_dir, filename)

#         print(f"📥 Downloading video: {video_url}")

#         headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"}
#         r = requests.get(
#             video_url, headers=headers, cookies=cookies, stream=True, timeout=15
#         )
#         r.raise_for_status()
#         with open(file_path, "wb") as f:
#             for chunk in r.iter_content(8192):
#                 f.write(chunk)

#         print(f"✅ Downloaded: {file_path}")

#         thumbnail = generate_video_thumbnail_pil(file_path, title)
#         return {"video_path": f"/public/videos/{filename}", "thumbnail": thumbnail}
#     except Exception as e:
#         print(f"❌ Download error: {e}")
#         return None


# def setup_firefox_driver():
#     """Setup optimized Firefox driver with minimal configuration."""
#     options = Options()

#     # Essential performance optimizations
#     options.add_argument("--headless")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--disable-extensions")
#     options.add_argument("--disable-plugins")
#     options.add_argument("--disable-images")
#     # options.add_argument("--disable-javascript")
#     options.add_argument("--disable-css")
#     options.add_argument("--disable-web-security")
#     options.add_argument("--disable-features=VizDisplayCompositor")

#     # Memory and performance optimizations
#     options.set_preference("browser.cache.disk.enable", False)
#     options.set_preference("browser.cache.memory.enable", False)
#     options.set_preference("browser.cache.offline.enable", False)
#     options.set_preference("network.http.use-cache", False)
#     options.set_preference("media.navigator.enabled", False)
#     options.set_preference("media.peerconnection.enabled", False)
#     options.set_preference("dom.webdriver.enabled", False)
#     options.set_preference("useAutomationExtension", False)

#     # User agent
#     options.set_preference(
#         "general.useragent.override",
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
#     )

#     service = Service(GeckoDriverManager().install())
#     return webdriver.Firefox(service=service, options=options)


# def download_tiktok_direct(url: str):
#     """Optimized TikTok video download using Selenium with minimal wait times."""
#     driver = None
#     try:
#         print("🚀 Starting optimized TikTok download...")
#         start_time = time.time()

#         driver = setup_firefox_driver()

#         # Navigate to URL
#         print("⏳ Loading page...")
#         driver.get(url)

#         # Wait for essential elements with shorter timeout
#         wait = WebDriverWait(driver, 8)  # Reduced from 15s to 8s

#         try:
#             # Wait for video element to be present
#             wait.until(EC.presence_of_element_located((By.TAG_NAME, "video")))
#             print("✅ Video element found")
#         except Exception:
#             print("⚠️ Video element not found, proceeding anyway...")

#         # Get page source and parse
#         page_source = driver.page_source
#         soup = BeautifulSoup(page_source, "html.parser")

#         # Extract title quickly
#         title = ""
#         element = soup.select_one('[data-e2e="new-desc-span"]')
#         if element:
#             title = element.get_text().strip()

#         if not title:
#             match = re.search(r"tiktok\.com/@([^/]+)", url)
#             username = match.group(1) if match else "tiktok_video"
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             title = f"{username}_{timestamp}"

#         title = " ".join(title.split()[:3])  # limit 3 words

#         # Extract video URLs efficiently
#         video_urls = []
#         for video in soup.find_all("video"):
#             if video.get("src"):
#                 video_urls.append(video["src"])
#             for source in video.find_all("source"):
#                 if source.get("src"):
#                     video_urls.append(source["src"])

#         # Extract cookies
#         cookies = {}
#         for cookie in driver.get_cookies():
#             cookies[cookie["name"]] = cookie["value"]

#         elapsed_time = time.time() - start_time
#         print(f"⏱️ Page processing completed in {elapsed_time:.2f}s")

#         if video_urls:
#             print(f"🎥 Found {len(video_urls)} video URL(s)")
#             dl = download_video_file(video_urls[0], title, cookies)
#             if dl:
#                 total_time = time.time() - start_time
#                 print(f"✅ Total processing time: {total_time:.2f}s")
#                 return {
#                     "title": title,
#                     "videolink": dl["video_path"],
#                     "thumbnail": dl["thumbnail"],
#                 }
#             else:
#                 return {"title": title, "videolink": None, "thumbnail": ""}
#         else:
#             return {"title": title, "videolink": None, "thumbnail": ""}

#     except Exception as e:
#         print(f"❌ Error: {e}")
#         return {"error": str(e)}
#     finally:
#         if driver:
#             driver.quit()


# async def fetch_tiktok_video(url: str):
#     """
#     Async wrapper for download_tiktok_direct.
#     Can be imported and called from any other file.
#     """
#     try:
#         # Run the synchronous function in a thread pool to avoid blocking
#         loop = asyncio.get_event_loop()
#         result = await loop.run_in_executor(None, download_tiktok_direct, url)
#         return result
#     except Exception as e:
#         print(f"❌ TikTok download error: {e}")
#         return {"error": str(e), "title": "", "videolink": None, "thumbnail": ""}
