from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL
import sys

app = Flask(__name__)

@app.route('/api', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    
    if not url:
        return jsonify({"success": False, "error": "Missing 'url' parameter. Usage: /api?url=your_link"}), 400

    # Configure yt-dlp to extract info only (no downloading, no playlists)
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': 'best', # Gets the best pre-merged video+audio stream
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # You can extract specific formats here if you want to offer 
            # separate audio/video options, but 'url' gives the best combined stream
            return jsonify({
                "success": True,
                "title": info.get('title', 'Unknown Title'),
                "thumbnail": info.get('thumbnail'),
                "duration_seconds": info.get('duration'),
                "view_count": info.get('view_count'),
                "uploader": info.get('uploader'),
                "direct_stream_url": info.get('url')
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Required for Vercel's Python environment
if __name__ == '__main__':
    app.run()
