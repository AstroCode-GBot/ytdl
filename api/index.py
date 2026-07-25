from flask import Flask, request, jsonify
import requests
import re

app = Flask(__name__)

def extract_video_id(url):
    """Extracts the 11-character YouTube video ID."""
    pattern = r'(?:youtube(?:-nocookie)?\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu\.be/)([^"&?/ ]{11})'
    match = re.search(pattern, url, re.IGNORECASE)
    return match.group(1) if match else None

@app.route('/api', methods=['GET'])
def get_video_info():
    video_url = request.args.get('url')
    
    # Your hardcoded API key
    api_key = "AIzaSyCaNa2PmZfYGU93vXQ-OVqR1beaquLGymU"
    
    if not video_url:
        return jsonify({"success": False, "error": "Missing 'url' parameter. Usage: /api?url=ytlink"}), 400

    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"success": False, "error": "Could not extract Video ID from URL."}), 400

    yt_api_url = f'https://www.youtube.com/youtubei/v1/player?key={api_key}'
    
    # The exact payload from your PHP script
    payload = {
        "context": {
            "client": {
                "hl": "en",
                "clientName": "WEB",
                "clientVersion": "2.20210721.00.00",
                "clientFormFactor": "UNKNOWN_FORM_FACTOR",
                "clientScreen": "WATCH",
                "mainAppWebInfo": {"graftUrl": f"/watch?v={video_id}"}
            },
            "user": {"lockedSafetyMode": False},
            "request": {"useSsl": True, "internalExperimentFlags": [], "consistencyTokenJars": []}
        },
        "videoId": video_id,
        "playbackContext": {
            "contentPlaybackContext": {
                "vis": 0, "splay": False, "autoCaptionsDefaultOn": False,
                "autonavState": "STATE_NONE", "html5Preference": "HTML5_PREF_WANTS", "lactMilliseconds": "-1"
            }
        },
        "racyCheckOk": False,
        "contentCheckOk": False
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate'
    }

    try:
        response = requests.post(yt_api_url, json=payload, headers=headers)
        meta = response.json()

        if 'streamingData' not in meta:
            return jsonify({
                "success": False, 
                "error": "No streaming data found. The video might be age-restricted or the request was blocked.",
                "raw_response": meta.get('playabilityStatus', meta)
            }), 400

        video_title = meta.get('videoDetails', {}).get('title', 'Unknown Title')
        formats = meta['streamingData'].get('formats', [])
        
        parsed_formats = []
        for fmt in formats:
            raw_mime = fmt.get('mimeType', '')
            
            if raw_mime:
                clean_mime = raw_mime.split(';')[0].split('/')[-1]
            else:
                clean_mime = 'mp4'
                
            parsed_formats.append({
                "url": fmt.get('url'),
                "mimeType": clean_mime,
                "quality": fmt.get('qualityLabel', fmt.get('quality', 'unknown')),
                "width": fmt.get('width'),
                "height": fmt.get('height')
            })

        return jsonify({
            "success": True,
            "title": video_title,
            "formats": parsed_formats
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run()
