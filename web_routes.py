import time
import os
import threading
import zipfile
from flask import  render_template, request, jsonify, session, Blueprint, redirect, url_for, send_file
import yt_dlp
from uuid import uuid4
from downloader_global import DOWNLOAD_FOLDER,download_sessions
from request_logger import log_request



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
                    try:
                        info = ydl.extract_info(url, download=True)
                        # Log the request
                        log_request(url, info, format_type, 'download')
                    except Exception as e:
                        # Try to extract info without downloading for logging
                        try:
                            ydl_opts_log = ydl_opts.copy()
                            ydl_opts_log['skip_download'] = True
                            with yt_dlp.YoutubeDL(ydl_opts_log) as ydl_log:
                                info = ydl_log.extract_info(url, download=False)
                                log_request(url, info, format_type, 'download')
                        except:
                            # Log with minimal info if extraction fails
                            log_request(url, None, format_type, 'download')
                        raise e
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

@web_bp.route('/admin')
def admin_panel():
    import os
    from datetime import datetime
    from downloader_global import DOWNLOAD_FOLDER
    
    files_info = []
    if os.path.exists(DOWNLOAD_FOLDER):
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)
                file_date = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                # Format file size
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                
                files_info.append({
                    'name': filename,
                    'size': size_str,
                    'size_bytes': file_size,
                    'date': file_date,
                    'path': file_path
                })
    
    # Sort by date (newest first)
    files_info.sort(key=lambda x: x['date'], reverse=True)
    
    # Calculate total size
    total_size = sum(f['size_bytes'] for f in files_info)
    if total_size < 1024 * 1024:
        total_size_str = f"{total_size / 1024:.2f} KB"
    else:
        total_size_str = f"{total_size / (1024 * 1024):.2f} MB"
    
    return render_template('admin.html', files=files_info, total_files=len(files_info), total_size=total_size_str)

@web_bp.route('/admin/delete-file', methods=['POST'])
def delete_file():
    import os
    from flask import request, jsonify
    from downloader_global import DOWNLOAD_FOLDER
    
    filename = request.json.get('filename')
    if not filename:
        return jsonify({"success": False, "error": "Filename is required"}), 400
    
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "File not found"}), 404
    
    try:
        os.remove(file_path)
        return jsonify({"success": True, "message": f"File {filename} deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@web_bp.route('/admin/requests')
def admin_requests():
    import json
    import os
    from request_logger import LOG_FILE
    
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            # Reverse to show newest first
            logs.reverse()
        except (json.JSONDecodeError, IOError):
            logs = []
    
    return render_template('admin_requests.html', requests=logs, total_requests=len(logs))

@web_bp.route('/admin/export-logs')
def export_logs():
    import json
    import os
    from flask import send_file
    from request_logger import LOG_FILE
    
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, as_attachment=True, download_name='request_logs.json')
    else:
        return "No logs file found", 404

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

