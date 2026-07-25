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

import yt_dlp
from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from pydantic import BaseModel, Field

# ==========================================
# CONFIGURATION
# ==========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ELITE_YTDL_API")

DOWNLOAD_DIR = Path("/tmp/ytdlp_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# YOUR PROVIDED DATA
USER_PROXY = "http://cejpdwtu:c9pexrhy2ymk@31.59.20.176:6754"
USER_COOKIES_B64 = "IyBOZXRzY2FwZSBIVFRQIENvb2tpZSBGaWxlCiMgaHR0cHM6Ly9jdXJsLmhheHguc2UvcmZjL2Nvb2tpZV9zcGVjLmh0bWwKIyBUaGlzIGlzIGEgZ2VuZXJhdGVkIGZpbGUhIERvIG5vdCBlZGl0LgoKLnlvdXR1YmUuY29tCVRSVUUJLwlGQUxTRQkxODE5NDc0MDMwCUhTSUQJQVlGcHJKejZGcjhlWTE2aEEKLnlvdXR1YmUuY29tCVRSVUUJLwlUUlVFCTE4MTk0NzQwMzAJU1NJRAlBa2FDMmkzNXZMcDM2R1k5egoueW91dHViZS5jb20JVFJVRQkvCUZBTFNFCTE4MTk0NzQwMzAJQVBJU0lECXFwUzUxRzhSX19ZWk1FRHkvQWx4YkVJcUdwTkJpWUM4NmcKLnlvdXR1YmUuY29tCVRSVUUJLwlUUlVFCTE4MTk0NzQwMzAJU0FQSVNJRAloREdEa09ScmpFVl8xX3F1L0FnU044QnJBWmRDMk9ySHU5Ci55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODE5NDc0MDMwCV9fU2VjdXJlLTFQQVBJU0lECWhER0RrT1JyakVWXzFfcXUvQWdTTjhCckFaZEMyT3JIdTkKLnlvdXR1YmUuY29tCVRSVUUJLwlUUlVFCTE4MTk0NzQwMzAJX19TZWN1cmUtM1BBUElTSUQJaERHRGtPUnJqRVZfMV9xdS9BZ1NOOEJyQVpkQzJPckh1OQoueW91dHViZS5jb20JVFJVRQkvCVRSVUUJMTgxOTQ3NDI4MQlQUkVGCWY2PTQwMDAwMDAwJnR6PUFzaWEuRGhha2EmZjc9MTAwCi55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODE2NDQ5OTg1CV9fU2VjdXJlLTFQU0lEVFMJc2lkdHMtQ2pRQlBXRXUyWEFBTkFEaEZwM3k3X28zaHpoUmFaRTBCSkI3UWpUZFBfYm5JRFFTMUZBVHNBMUhFUngwX3Z6UmhYUDdLdmJ4RUFBCi55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODE2NDQ5OTg1CV9fU2VjdXJlLTNQU0lEVFMJc2lkdHMtQ2pRQlBXRXUyWEFBTkFEaEZwM3k3X28zaHpoUmFaRTBCSkI3UWpUZFBfYm5JRFFTMUZBVHNBMUhFUngwX3Z6UmhYUDdLdmJ4RUFBCi55b3V0dWJlLmNvbQlUUlVFCS8JRkFMU0UJMTgxOTQ3NDAzMAlTSUQJZy5hMDAwQXdtUlRKNERfSmJGTzBLbE9sY2FvVWtON0g0dnV1NnFlWTQ2ZGZLNkl5R1plVkliNGpNbGw1M1hCYXpZWVBRd0Q1VkJUQUFDZ1lLQVM0U0FSWVNGUUhHWDJNaW9yN1BOUEdTTkJjNWNZX1gyV0ZNYWhvVkFVRjh5S3BRaTltNlRYOEVjdEFCZUx4S2ZULWgwMDc2Ci55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODE5NDc0MDMwCV9fU2VjdXJlLTFQU0lECWcuYTAwMEF3bVJUSjREX0piRk8wS2xPbGNhb1VrTjdINHZ1dTZxZVk0NmRmSzZJeUdaZVZJYjN4WkRfbnRzbWdwbzZkcXF2R0wyYXdBQ2dZS0FUWVNBUllTRlFIR1gyTWk0SkJLNFZ2ckVweTBuS3drUHRFdGF4b1ZBVUY4eUtyTE9Cb1h5ZXpFUWRDS19OUGozZjN1MDA3NgoueW91dHViZS5jb20JVFJVRQkvCVRSVUUJMTgxOTQ3NDAzMAlfX1NlY3VyZS0zUFNJRAlnLmEwMDBBd21SVEo0RF9KYkZPMEtsT2xjYW9Va043SDR2dXU2cWVZNDZkZks2SXlHWmVWSWJRRnRrYWlZUW5EbjE0blV1UXFSQUFRQUNnWUtBUW9TQVJZU0ZRSEdYMk1pMFpJamNjZnVHeUFOaktwR0dEN2hhaG9WQVVGOHlLcURPNnJwblNQd0dqOW1PVGQtUXVuQzAwNzYKLnlvdXR1YmUuY29tCVRSVUUJLwlUUlVFCTE4MTk0NzQyNzcJTE9HSU5fSU5GTwlBRm1tRjJzd1JBSWdUVDRENU1HNGp5QmtKbTR3VEcteW9nV0dZVVd4aGlIcW0yVHdPSFhoS3JrQ0lFWXJxeEFDMzB4bldvbXJxRVZUcHdVdEZKOEY1YXQxNDJqcXB3RFdVaVRXOlFVUTNNak5tZW5sNU0xVmxWRTF2WDFwVFpTMDNjVXBQUlRSUWMwRnVhMkp4Y0RoTGEwVTVPVnBrZVRWV2FuTjZVMnhIVW1oWU9GcHphbGx4TTNKR2NrRjFUMVJvTjJoUllreDBTVjlGVVVOWFRYTnJjRFkyY2tGSVREQmZSa1JRZUdveFdHVkpOMFZRYjBsYU5uTXllbEpWWjE4eVNUZFdXbDlvUzA1QmRtTnVSSFp2Vm5wcFJucHZkSGhhUjE5MVRXZFNkVUV0YjFnMGEzVkNOM3BOVkhoUgoueW91dHViZS5jb20JVFJVRQkvCVRSVUUJMTc4NDkxNDg4MQlDT05TSVNURU5DWQlBRmVoZVcwd3phZEczS29PN0dDeWlUQXdjMUYwMVNsc3Ezdk5rXy1Ja2tvaVFVRXlCMU5VdjMyTUxEcXNTc042cGpaZjYzd1Y4YU5zVUFrZ0VFdjVUOE9welFpREh0OHpsSTc5T1dHRW1sWlJqcVlhOFF1SVRVc0h2cmFoeVQ1OGxJT2lheEQ2UkFfZ1BNMl9iS05KVnljZwoueW91dHViZS5jb20JVFJVRQkvCUZBTFNFCTE4MTY0NTAyODcJU0lEQ0MJQUtFeVh6V01KLVJObng5NThkVEF6YklRc2poZUk2NkRjaU53ZU5EQWdVb0ZBM3ZKWHJRUFZZZDhmVW5rU2FQd1dMa19jUy1KNW1FCi55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODE2NDUwMjg3CV9fU2VjdXJlLTFQU0lEQ0MJQUtFeVh6WC02ZGlQUGFsNFdoaTM1dV9HWE9qcGtzUGdKSDMxcDFLb0NQSFRHRHFXZC1YR0ZDRUFhQ3hJVzJ3Ui1XZ0NaNU9kc3cKLnlvdXR1YmUuY29tCVRSVUUJLwlUUlVFCTE4MTY0NTAyODcJX19TZWN1cmUtM1BTSURDQwlBS0V5WHpWa2EtMF9xLTQ5MmtXck1KVHZtOWtPa0FacWM1c3ZJd29UN0R1SzZkdFNiazJKNFVBR0pFbFBTM3l2MEVEQjU5Z2t1UQoueW91dHViZS5jb20JVFJVRQkvCVRSVUUJMTgwMDQ2NjI4NwlWSVNJVE9SX0lORk8xX0xJVkUJZHpDS0gxeGlIUWcKLnlvdXR1YmUuY29tCVRSVUUJLwlUUlVFCTE4MDA0NjYyODcJVklTSVRPUl9QUklWQUNZX01FVEFEQVRBCUNnSkNSQklFR2dBZ1NBJTNEJTNECi55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODAwNDMyOTM5CV9fU2VjdXJlLVlOSUQJMjAuWVQ9VHA1ZERISkJKV3JIWF9DY0xPT2ZMdHBVdjNoU0dzNzNWSXhMLTFvdERVc2h6bDcxWlF6S2I1VzVCWDJKUllmdXZkRi1peGNvaUVyel9VaFB0cFNXS0s4aUw2dlhuU3Z2eDNabFRQaFBNc3YtRlZHX202dXlmenR4OWRseGtnb190ak5uckF1SXVVUXlQcDBlVVk0MXpqSmVfZWhqeEhjOFc1b2w1amdmY2NUWlhCSEJ3bnNvNWl1Q1BoZEszaW9yMEVRZzlCdkZlOEtqcURfYkF1eDZJQXNvUDd0VG5tN1VDUkxxdDVCZFZBUWxCQkFaUHAzeVV2WmhuSm5uN0ZHdU1zUFpmMmVUQmlnNHhjbDNvR2ZGa1JMNnNiWjBDSmpBdllYYVFRWXJOWVVRWnZINmUwYzRzeENRN3ZOamV1TV81WWxFelY2aUNqMnBNaDZWLUNQSUpRCi55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkxODAwNDMyOTM5CV9fU2VjdXJlLVJPTExPVVRfVE9LRU4JQ095M3VabnUyT0RkZ1FFUTFiNlA0NmpWbFFNWXlfUzIwdV9xbFFNJTNECi55b3V0dWJlLmNvbQlUUlVFCS8JVFJVRQkwCVlTQwlzc3R0Q3B4cjc3OAo="

app = FastAPI(title="Pro YT Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# MODELS
# ==========================================

class DownloadRequest(BaseModel):
    url: str
    format_id: Optional[str] = "bestvideo+bestaudio/best"

class AudioRequest(BaseModel):
    url: str
    ext: str = "mp3"

# ==========================================
# CORE LOGIC
# ==========================================

def get_cookie_file():
    cookie_path = "/tmp/youtube_cookies.txt"
    with open(cookie_path, "wb") as f:
        f.write(base64.b64decode(USER_COOKIES_B64))
    return cookie_path

class YTManager:
    @staticmethod
    def get_ydl_opts(extra_opts: Dict = None) -> Dict:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'proxy': USER_PROXY,
            'cookiefile': get_cookie_file(),
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'socket_timeout': 30,
            'retries': 5,
        }
        if extra_opts:
            opts.update(extra_opts)
        return opts

    @classmethod
    async def run_async(cls, url: str, download: bool = False, extra_opts: Dict = None):
        def _exec():
            with yt_dlp.YoutubeDL(cls.get_ydl_opts(extra_opts)) as ydl:
                return ydl.extract_info(url, download=download)
        return await asyncio.to_thread(_exec)

async def auto_delete(file_path: str):
    await asyncio.sleep(600) # Delete after 10 mins
    if os.path.exists(file_path):
        os.remove(file_path)

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    return {"status": "online", "proxy": "active", "cookies": "loaded"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api")
async def api_info_downloader(url: str = Query(..., alias="url")):
    """Custom endpoint requested: /api?url=yturl"""
    try:
        info = await YTManager.run_async(url, download=False)
        return {
            "title": info.get("title"),
            "id": info.get("id"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "views": info.get("view_count"),
            "formats": [
                {"id": f["format_id"], "ext": f["ext"], "res": f.get("resolution"), "note": f.get("format_note")}
                for f in info.get("formats", []) if f.get("vcodec") != "none"
            ]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/info")
async def get_info(url: str):
    return await api_info_downloader(url)

@app.get("/formats")
async def get_formats(url: str):
    info = await YTManager.run_async(url)
    return {"formats": info.get("formats")}

@app.post("/download")
async def post_download(req: DownloadRequest, tasks: BackgroundTasks):
    try:
        uid = str(uuid.uuid4())
        path_tmpl = str(DOWNLOAD_DIR / f"{uid}.%(ext)s")
        
        info = await YTManager.run_async(req.url, download=True, extra_opts={
            'format': req.format_id,
            'outtmpl': path_tmpl,
            'merge_output_format': 'mp4'
        })
        
        ext = info.get('ext', 'mp4')
        final_file = DOWNLOAD_DIR / f"{uid}.{ext}"
        tasks.add_task(auto_delete, str(final_file))
        
        safe_name = re.sub(r'[^\w\-.]', '_', info['title'])
        return {
            "success": True,
            "filename": f"{safe_name}.{ext}",
            "download_url": f"/stream/{uid}.{ext}?name={safe_name}.{ext}",
            "size": info.get("filesize")
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/audio")
async def post_audio(req: AudioRequest, tasks: BackgroundTasks):
    try:
        uid = str(uuid.uuid4())
        path_tmpl = str(DOWNLOAD_DIR / f"{uid}.%(ext)s")
        
        info = await YTManager.run_async(req.url, download=True, extra_opts={
            'format': 'bestaudio/best',
            'outtmpl': path_tmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': req.ext,
                'preferredquality': '192',
            }],
        })
        
        final_file = DOWNLOAD_DIR / f"{uid}.{req.ext}"
        tasks.add_task(auto_delete, str(final_file))
        
        safe_name = re.sub(r'[^\w\-.]', '_', info['title'])
        return {
            "success": True,
            "filename": f"{safe_name}.{req.ext}",
            "download_url": f"/stream/{uid}.{req.ext}?name={safe_name}.{req.ext}"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/thumbnail")
async def get_thumb(url: str):
    info = await YTManager.run_async(url)
    return RedirectResponse(info.get("thumbnail"))

@app.get("/captions")
async def get_captions(url: str):
    info = await YTManager.run_async(url)
    return {"subtitles": info.get("subtitles"), "auto": info.get("automatic_captions")}

@app.get("/playlist")
async def get_playlist(url: str):
    info = await YTManager.run_async(url, extra_opts={'extract_flat': True})
    return {"title": info.get("title"), "videos": info.get("entries")}

@app.get("/search")
async def search_yt(q: str):
    info = await YTManager.run_async(f"ytsearch5:{q}", extra_opts={'extract_flat': True})
    return {"results": info.get("entries")}

@app.get("/stream/{file_id}")
async def serve_file(file_id: str, name: str = "video.mp4"):
    file_path = DOWNLOAD_DIR / file_id
    if not file_path.exists() or ".." in file_id:
        raise HTTPException(status_code=404, detail="File not found or expired")
    return FileResponse(file_path, filename=name)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
