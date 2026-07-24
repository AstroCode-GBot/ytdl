import asyncio
import logging
import os
import re
import time
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import yt_dlp
from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yt_downloader_api")

DOWNLOAD_DIR = Path("/tmp/ytdlp_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Environment Variables for Geo-Bypass
# Set these in your Vercel/Server Dashboard
PROXY_URL = os.getenv("PROXY_URL") # Example: http://user:pass@host:port
YT_COOKIES_BASE64 = os.getenv("YT_COOKIES_BASE64") # Base64 encoded cookies.txt content

# Simple In-Memory Rate Limiter
request_history: Dict[str, List[float]] = {}
RATE_LIMIT = 50 
RATE_LIMIT_WINDOW = 60 

app = FastAPI(
    title="Elite YouTube Downloader API",
    description="High-performance YouTube downloader API with Geo-Bypass support",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# MODELS
# ==========================================

class DownloadRequest(BaseModel):
    url: str = Field(..., description="The YouTube URL")
    format_id: Optional[str] = Field("bestvideo+bestaudio/best", description="yt-dlp format selection")

class AudioRequest(BaseModel):
    url: str = Field(..., description="The YouTube URL")
    ext: str = Field("mp3", pattern="^(mp3|m4a|aac|wav|opus|flac)$")

class VideoInfoResponse(BaseModel):
    title: str
    description: Optional[str]
    duration: Optional[int]
    views: Optional[int]
    channel: Optional[str]
    upload_date: Optional[str]
    thumbnail: Optional[str]
    formats: List[Dict[str, Any]]
    filesize: Optional[int]
    fps: Optional[int]
    resolution: Optional[str]
    codec: Optional[str]
    bitrate: Optional[float]
    language: Optional[str]
    tags: List[str]
    categories: List[str]
    is_live: bool
    was_live: bool
    availability: Optional[str]
    age_limit: int
    chapters: List[Dict[str, Any]]

# ==========================================
# UTILS & MIDDLEWARE
# ==========================================

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

def is_valid_youtube_url(url: str) -> bool:
    pattern = r"^(https?://)?(www\.|m\.)?(youtube\.com|youtu\.be|youtube-nocookie\.com|youtube\.com/shorts/)/.+$"
    return bool(re.match(pattern, url))

async def cleanup_file(file_path: str, delay: int = 600):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up: {file_path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    now = time.time()
    request_history[client_ip] = [t for t in request_history.get(client_ip, []) if now - t < RATE_LIMIT_WINDOW]
    if len(request_history[client_ip]) >= RATE_LIMIT:
        return JSONResponse(status_code=HTTP_429_TOO_MANY_REQUESTS, content={"error": "Rate limit exceeded"})
    request_history[client_ip].append(now)
    return await call_next(request)

# ==========================================
# YT-DLP CORE LOGIC (ENHANCED)
# ==========================================

class YTManager:
    @staticmethod
    def get_opts(custom_opts: Dict = None) -> Dict:
        # 1. Setup Cookie Path if provided via Environment Variable
        cookie_path = None
        if YT_COOKIES_BASE64:
            try:
                cookie_path = "/tmp/cookies.txt"
                with open(cookie_path, "wb") as f:
                    f.write(base64.b64decode(YT_COOKIES_BASE64))
            except Exception as e:
                logger.error(f"Failed to decode cookies: {e}")

        base_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
            'socket_timeout': 30,
            'retries': 5,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US', # Force bypass from US region
            'extract_flat': False,
            'proxy': PROXY_URL, 
            'cookiefile': cookie_path,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/',
            }
        }
        if custom_opts:
            base_opts.update(custom_opts)
        return base_opts

    @classmethod
    async def extract(cls, url: str, download: bool = False, custom_opts: Dict = None):
        def _run():
            with yt_dlp.YoutubeDL(cls.get_opts(custom_opts)) as ydl:
                return ydl.extract_info(url, download=download)
        return await asyncio.to_thread(_run)

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {"status": "online", "geo_bypass": "enabled", "proxy_status": "configured" if PROXY_URL else "none"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/info", response_model=VideoInfoResponse)
async def get_info(url: str = Query(...)):
    if not is_valid_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    try:
        info = await YTManager.extract(url, download=False)
        return VideoInfoResponse(
            title=info.get("title", "N/A"),
            description=info.get("description", ""),
            duration=info.get("duration"),
            views=info.get("view_count"),
            channel=info.get("uploader"),
            upload_date=info.get("upload_date"),
            thumbnail=info.get("thumbnail"),
            formats=[{
                "format_id": f.get("format_id"),
                "extension": f.get("ext"),
                "resolution": f.get("resolution"),
                "filesize": f.get("filesize"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec")
            } for f in info.get("formats", [])],
            filesize=info.get("filesize_approx") or info.get("filesize"),
            fps=info.get("fps"),
            resolution=f"{info.get('width')}x{info.get('height')}" if info.get('width') else None,
            codec=info.get("vcodec"),
            bitrate=info.get("tbr"),
            language=info.get("language"),
            tags=info.get("tags", []),
            categories=info.get("categories", []),
            is_live=info.get("is_live", False),
            was_live=info.get("was_live", False),
            availability=info.get("availability"),
            age_limit=info.get("age_limit", 0),
            chapters=info.get("chapters", [])
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/formats")
async def get_formats(url: str = Query(...)):
    try:
        info = await YTManager.extract(url)
        return {"formats": info.get("formats", [])}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/download")
async def download_video(req: DownloadRequest, background_tasks: BackgroundTasks):
    try:
        unique_id = str(uuid.uuid4())
        output_tmpl = str(DOWNLOAD_DIR / f"{unique_id}.%(ext)s")
        
        info = await YTManager.extract(req.url, download=True, custom_opts={
            'format': req.format_id,
            'outtmpl': output_tmpl,
            'merge_output_format': 'mp4',
        })
        
        ext = info.get('ext', 'mp4')
        actual_path = DOWNLOAD_DIR / f"{unique_id}.{ext}"
        background_tasks.add_task(cleanup_file, str(actual_path))
        
        return {
            "success": True,
            "filename": f"{sanitize_filename(info['title'])}.{ext}",
            "download_url": f"/stream/{unique_id}.{ext}?name={sanitize_filename(info['title'])}.{ext}",
            "size": info.get("filesize_approx") or info.get("filesize"),
            "duration": info.get("duration")
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/audio")
async def download_audio(req: AudioRequest, background_tasks: BackgroundTasks):
    try:
        unique_id = str(uuid.uuid4())
        output_tmpl = str(DOWNLOAD_DIR / f"{unique_id}.%(ext)s")
        
        info = await YTManager.extract(req.url, download=True, custom_opts={
            'format': 'bestaudio/best',
            'outtmpl': output_tmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': req.ext,
                'preferredquality': '192',
            }],
        })
        
        actual_path = DOWNLOAD_DIR / f"{unique_id}.{req.ext}"
        background_tasks.add_task(cleanup_file, str(actual_path))
        
        return {
            "success": True,
            "filename": f"{sanitize_filename(info['title'])}.{req.ext}",
            "download_url": f"/stream/{unique_id}.{req.ext}?name={sanitize_filename(info['title'])}.{req.ext}",
            "duration": info.get("duration")
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/thumbnail")
async def get_thumbnail(url: str = Query(...)):
    try:
        info = await YTManager.extract(url)
        return RedirectResponse(info.get("thumbnail"))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/playlist")
async def get_playlist(url: str = Query(...)):
    try:
        info = await YTManager.extract(url, custom_opts={'extract_flat': True})
        return {
            "title": info.get("title"),
            "videos": [{"id": e.get("id"), "title": e.get("title"), "url": e.get("url")} for e in info.get("entries", [])]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/search")
async def search(q: str = Query(...)):
    try:
        info = await YTManager.extract(f"ytsearch5:{q}", custom_opts={'extract_flat': True})
        return {"results": info.get("entries", [])}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/stream/{file_id}")
async def stream_file(file_id: str, name: str = "download"):
    file_path = DOWNLOAD_DIR / file_id
    if not file_path.exists() or ".." in file_id:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=name)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
