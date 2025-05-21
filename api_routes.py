import os
import threading
from flask import  request,  jsonify,  Blueprint
import yt_dlp
from uuid import uuid4
from downloader_global import DOWNLOAD_FOLDER,download_sessions

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/progress', methods=['GET'])
def get_progress_api():
    session_id = request.headers.get('X-Session-ID')
    return jsonify(download_sessions.get(session_id, {
        "percent": "0%",
        "status": "Idle",
        "filename": None,
        "size": None
    }))
@api_bp.route('/api/download', methods=['POST'])
def api_download():
    urls = request.form.get('url').strip().splitlines()
    format_type = request.form.get('format')
    playlist = request.form.get('playlist') == 'on'
    quality = request.form.get('quality') or "best"
    session_id = request.headers.get('X-Session-ID') or str(uuid4())

    download_sessions[session_id] = {
        "percent": "0%",
        "status": "Downloading",
        "filename": None,
        "size": None
    }

    def progress_hook(d):
        if d['status'] == 'downloading':
            download_sessions[session_id]['percent'] = d.get('_percent_str', '0.0%').strip()
            download_sessions[session_id]['status'] = "Downloading"
        elif d['status'] == 'finished':
            download_sessions[session_id]['percent'] = "100%"
            download_sessions[session_id]['status'] = "Processing..."

    def download():
        try:
            ydl_opts = {
                'progress_hooks': [progress_hook],
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'format': quality,
                'noplaylist': not playlist,
                'quiet': True,
                'merge_output_format': format_type if format_type in ['mp4', 'mkv', 'webm', 'mp3'] else None,
                'cookiefile': 'app/cookies.txt',
            }

            if format_type == 'audio':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(urls)

            # After download, find the latest file added to the downloads folder
            files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER)]
            if files:
                latest_file = max(files, key=os.path.getctime)
                filename = os.path.basename(latest_file)
                download_sessions[session_id]['filename'] = filename
                download_sessions[session_id]['status'] = "Completed"
            else:
                download_sessions[session_id]['status'] = "Error: No file found after download"

        except Exception as e:
            download_sessions[session_id]['status'] = f"Error: {str(e)}"
            download_sessions[session_id]['filename'] = None

    threading.Thread(target=download, daemon=True).start()
    return jsonify({"success": True, "session_id": session_id})


@api_bp.route('/api/cancel', methods=['POST'])
def cancel_download():
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id or session_id not in download_sessions:
        return jsonify({"success": False, "error": "Invalid session ID"}), 400

    # Implement logic to cancel the ongoing download thread/task here
    # For example, set a flag or terminate the thread safely

    # Mark session as cancelled
    download_sessions[session_id]['status'] = "Cancelled"
    # You should implement the actual download stopping logic depending on your download implementation.

    return jsonify({"success": True})





