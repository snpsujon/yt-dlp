import time
import os
import threading
import zipfile
from flask import Flask, render_template, request, send_from_directory, jsonify, session
import yt_dlp
from uuid import uuid4

app = Flask(__name__)
app.secret_key = 'your-secret-key'

DOWNLOAD_FOLDER = 'static/downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_sessions = {}

@app.route('/')
def index():
    session_id = session.get('id')
    progress = download_sessions.get(session_id, {
        "percent": "0%",
        "status": "Idle",
        "filename": None,
        "size": None
    })
    return render_template(
        'index.html',
        status=progress['status'],
        error=None,
        url="",
        format="video",
        size=progress['size'],
        quality="best"
    )

@app.route('/download', methods=['POST'])
def download_video():
    urls = request.form.get('url').strip().splitlines()
    format_type = request.form.get('format')
    playlist = request.form.get('playlist') == 'on'
    quality = request.form.get('quality') or "best"
    session_id = session.setdefault('id', str(uuid4()))

    if not urls:
        return render_template('index.html', error="Please enter at least one URL.", status="Idle")

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
            timestamp = int(time.time())
            ext = 'mp3' if format_type == 'audio' else 'mp4'
            base_name = f'download_{timestamp}'
            out_files = []

            for idx, url in enumerate(urls):
                output_name = f"{base_name}_{idx}"
                output_template = os.path.join(DOWNLOAD_FOLDER, f"{output_name}.%(ext)s")

                ydl_opts = {
                    'progress_hooks': [progress_hook],
                    'outtmpl': output_template,
                    'noplaylist': not playlist,
                    'format': quality,
                    'quiet': True,
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
                    info = ydl.extract_info(url, download=True)
                    filesize = info.get('filesize') or info.get('filesize_approx')
                    if filesize:
                        mb_size = round(filesize / (1024 * 1024), 2)
                        download_sessions[session_id]['size'] = f"{mb_size} MB"
                    else:
                        download_sessions[session_id]['size'] = "Unknown"
                    if isinstance(info, dict):
                        filename = ydl.prepare_filename(info)
                        if format_type == 'audio':
                            filename = filename.rsplit('.', 1)[0] + ".mp3"
                        out_files.append(filename)

            if len(out_files) > 1:
                zip_name = f"{base_name}.zip"
                zip_path = os.path.join(DOWNLOAD_FOLDER, zip_name)
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file_path in out_files:
                        zipf.write(file_path, os.path.basename(file_path))
                download_sessions[session_id]['filename'] = zip_name
            else:
                download_sessions[session_id]['filename'] = os.path.basename(out_files[0])

            total_size = sum(os.path.getsize(f) for f in out_files)
            # download_sessions[session_id]['size'] = f"{round(total_size / (1024 * 1024), 2)} MB"
            download_sessions[session_id]['status'] = "Completed"

        except Exception as e:
            download_sessions[session_id]['status'] = f"Error: {str(e)}"
            download_sessions[session_id]['filename'] = None

    threading.Thread(target=download, daemon=True).start()

    return render_template(
        'index.html',
        status="Downloading",
        error=None,
        url="\n".join(urls),
        format=format_type,
        size=download_sessions[session_id]['size'],
        quality=quality
    )

@app.route('/progress')
def get_progress():
    session_id = session.get('id')
    return jsonify(download_sessions.get(session_id, {
        "percent": "0%",
        "status": "Idle",
        "filename": None,
        "size": None
    }))

@app.route('/downloads/<filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    else:
        return "File not found", 404

def auto_delete_old_files():
    while True:
        now = time.time()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > 600:
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
        time.sleep(60)

threading.Thread(target=auto_delete_old_files, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
