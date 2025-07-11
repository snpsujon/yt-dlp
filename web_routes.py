import time
import os
import threading
import zipfile
from flask import  render_template, request, jsonify, session, Blueprint, redirect, url_for
import yt_dlp
from uuid import uuid4
from downloader_global import DOWNLOAD_FOLDER,download_sessions



web_bp = Blueprint('web', __name__)
@web_bp.route('/')
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

@web_bp.route('/download', methods=['GET', 'POST'])
def download_video():
    if request.method == 'GET':
        return redirect(url_for('web.index'))

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

@web_bp.route('/progress')
def get_progress():
    session_id = session.get('id')
    return jsonify(download_sessions.get(session_id, {
        "percent": "0%",
        "status": "Idle",
        "filename": None,
        "size": None
    }))


@web_bp.route('/privacy')
def privacy_policy():
    return render_template('privacy.html')

@web_bp.route('/get_audio_formats', methods=['POST'])
def get_formats():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL missing'}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'force_generic_extractor': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

            mp4_formats = []
            audio_formats = []

            for f in formats:
                # MP4 video with video codec
                if f.get('ext') == 'mp4' and f.get('vcodec') != 'none':
                    mp4_formats.append({
                        'format_id': f.get('format_id'),
                        'quality': f.get('format_note') or f.get('height'),
                        'url': f.get('url'),
                    })
                # MP3 or M4A (audio only)
                elif f.get('vcodec') == 'none' and f.get('ext') in ['mp3', 'm4a']:
                    audio_formats.append({
                        'format_id': f.get('format_id'),
                        'language': f.get('language') or f.get('format_note') or 'Unknown',
                        'url': f.get('url'),
                        'ext': f.get('ext'),
                    })

            return jsonify({
                'video_formats': mp4_formats,
                'audio_formats': audio_formats
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

