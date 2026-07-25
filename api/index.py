from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "endpoint": "/api?url=https://youtube.com/watch?v=..."
    })

@app.route("/api")
def api():
    url = request.args.get("url")

    if not url:
        return jsonify({"error": "Missing url"}), 400

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "formats": [
                {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "height": f.get("height"),
                    "url": f.get("url")
                }
                for f in info.get("formats", [])
                if f.get("url")
            ]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Vercel looks for `app`
