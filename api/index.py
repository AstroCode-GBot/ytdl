from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "endpoint": "/api?url=https://www.youtube.com/watch?v=VIDEO_ID"
    })

@app.route("/api")
def api():
    url = request.args.get("url")

    if not url:
        return jsonify({"success": False, "error": "Missing url parameter"}), 400

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []

        for f in info.get("formats", []):
            if not f.get("url"):
                continue

            formats.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f"{f.get('width')}x{f.get('height')}" if f.get("height") else None,
                "fps": f.get("fps"),
                "filesize": f.get("filesize"),
                "url": f.get("url")
            })

        return jsonify({
            "success": True,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "view_count": info.get("view_count"),
            "formats": formats
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
