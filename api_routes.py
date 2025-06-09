import os
import re
import threading
from collections import defaultdict

import pycountry
import unicodedata
from flask import request, jsonify, Blueprint
import yt_dlp
from uuid import uuid4
from downloader_global import DOWNLOAD_FOLDER, download_sessions

api_bp = Blueprint('api', __name__)

def sanitize_filename(filename):
    # Normalize to remove accents and convert to ASCII
    nfkd_form = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')

    # Replace spaces with underscores and remove non-alphanumeric characters
    sanitized = re.sub(r'[^\w\s.-]', '', only_ascii)  # Keep alphanumeric, dot, dash, underscore
    sanitized = re.sub(r'\s+', '_', sanitized)  # Replace spaces with underscores
    return sanitized[:10]

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

            # After download, find the latest file
            files = [os.path.join(DOWNLOAD_FOLDER, f) for f in os.listdir(DOWNLOAD_FOLDER)]
            if files:
                latest_file = max(files, key=os.path.getctime)
                filename = os.path.basename(latest_file)

                # Sanitize filename
                sanitized_name = sanitize_filename(os.path.splitext(filename)[0])
                ext = os.path.splitext(filename)[1]
                sanitized_full_path = os.path.join(DOWNLOAD_FOLDER, sanitized_name + ext)

                os.rename(latest_file, sanitized_full_path)

                download_sessions[session_id]['filename'] = os.path.basename(sanitized_full_path)
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

    download_sessions[session_id]['status'] = "Cancelled"
    return jsonify({"success": True})


# @api_bp.route('/api/direct-links-all-format', methods=['POST'])
def get_direct_links_all_format():
    url = request.form.get('url')
    # url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'cookiefile': 'app/cookies.txt',
        }

        direct_links = []


        def extract_urls(info_dict):
            formats = info_dict.get('formats', [])
            for fmt in formats:
                if fmt.get('url') and fmt.get('ext') in ['mp4', 'webm', 'm4a', 'mp3']:
                    direct_links.append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': fmt.get('resolution') or f"{fmt.get('width', '')}x{fmt.get('height', '')}",
                        'url': fmt.get('url'),
                        'filesize': fmt.get('filesize') or fmt.get('filesize_approx'),
                    })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:  # It's a playlist
                for entry in info['entries']:
                    extract_urls(entry)
            else:
                extract_urls(info)

        return jsonify({"success": True, "links": direct_links})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



def parse_resolution(res_str):
    # Simple helper to parse resolution string like "1280x720" or "720p"
    if not res_str:
        return {"width": None, "height": None}
    if 'x' in res_str:
        parts = res_str.lower().split('x')
        try:
            width = int(parts[0])
            height = int(parts[1])
            return {"width": width, "height": height}
        except:
            return {"width": None, "height": None}
    elif res_str.endswith('p'):
        try:
            height = int(res_str[:-1])
            return {"width": None, "height": height}
        except:
            return {"width": None, "height": None}
    return {"width": None, "height": None}

def filesize_human_readable(size_bytes):
    # Convert bytes to human-readable format (optional)
    if not size_bytes:
        return None
    for unit in ['B','KB','MB','GB','TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def get_language_name(code):
    try:
        language = pycountry.languages.get(alpha_2=code)
        return language.name if language else "Default"
    except:
        return "Default"


@api_bp.route('/api/direct-links', methods=['GET', 'POST'])
def get_direct_links():
    if request.method == 'POST':
        url = request.form.get('url')
        format_type = request.form.get('format')
    else:  # GET
        url = request.args.get('url')
        format_type = request.args.get('format')

    if not url:
        return jsonify({"error": "URL is required"}), 400
    if format_type not in ('video', 'audio'):
        return jsonify({"error": "Format must be 'video' or 'audio'"}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'cookiefile': 'app/cookies.txt',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36'
        }

        grouped_links = defaultdict(list)
        v_info = defaultdict(list)

        def extract_urls(info_dict):
            formats = info_dict.get('formats', [])
            for fmt in formats:
                ext = fmt.get('ext')
                url_ = fmt.get('url')
                if not url_ or not ext:
                    continue

                # Filtering by format type
                if format_type == 'video':
                    # skip audio only formats
                    if fmt.get('vcodec') == 'none':
                        continue
                    # ✅ new line: skip video-only formats without audio
                    # if fmt.get('acodec') == 'none':
                    #     continue
                    # Accept common video formats (mp4, webm, mkv)
                    if ext not in ['mp4', 'webm', 'mkv']:
                        continue
                else:  # audio
                    # skip video only formats
                    if fmt.get('acodec') == 'none':
                        continue
                    # Accept common audio formats
                    if ext not in ['mp3', 'm4a', 'webm', 'aac', 'opus']:
                        continue

                # Determine resolution or quality label
                resolution = fmt.get('resolution')
                if not resolution:
                    width = fmt.get('width')
                    height = fmt.get('height')
                    if width and height:
                        resolution = f"{width}x{height}"
                    else:
                        resolution = ''



                filesize_bytes = fmt.get('filesize') or fmt.get('filesize_approx')


                link_info = {
                    'format_id': fmt.get('format_id'),
                    'language_code': fmt.get('language') or 'Default',
                    'language': get_language_name(fmt.get('language') or fmt.get('format_note')),
                    'ext': ext,
                    'resolution': resolution,
                    'url': url_,
                    'downloadQuality': fmt.get('height') or fmt.get('format_id'),
                    'filesize_bytes': filesize_bytes,
                    'filesize_readable': filesize_human_readable(filesize_bytes),
                    'format_note': fmt.get('format_note')
                }
                if fmt.get('vcodec') != 'none' and fmt.get('acodec') == 'none':
                    link_info['note'] = 'Video Only (No Audio)'

                grouped_links[ext].append(link_info)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:  # playlist
                for entry in info['entries']:
                    extract_urls(entry)
            else:
                extract_urls(info)

            v_info['title'] = (info.get('title', 'Unknown Title'))
            v_info['description'] = (info.get('description', ''))
            v_info['channel'] = (info.get('channel', ''))
            v_info['channel_id'] = (info.get('channel_id', ''))
            v_info['channel_url'] = (info.get('channel_url', ''))
            v_info['channel_subscriber'] = (info.get('channel_follower_count', ''))
            v_info['comment_count'] = (info.get('comment_count', ''))
            v_info['video_id'] = (info.get('display_id', ''))
            v_info['duration'] = (info.get('duration_string', ''))
            v_info['thumbnail'] = (info.get('thumbnail', ''))
            v_info['upload_date'] = (info.get('upload_date', ''))
            v_info['view_count'] = (info.get('view_count', ''))
            v_info['uploader_id'] = (info.get('uploader_id', ''))
            v_info['uploader'] = (info.get('uploader', ''))
            v_info['platform'] = (info.get('extractor_key', ''))
            v_info['like_count'] = (info.get('like_count', ''))
            v_info['concurrent_view_count'] = (info.get('concurrent_view_count', ''))


        if not grouped_links:
            return jsonify({"success": False, "error": "No matching formats found"}), 404

        return jsonify({
            "success": True,
            "info": v_info,
            "links": grouped_links,
        })


    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

