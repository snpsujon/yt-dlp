import os
import re
import threading
from collections import defaultdict

import pycountry
import unicodedata
from flask import request, jsonify, Blueprint, render_template
import yt_dlp
from uuid import uuid4
from downloader_global import DOWNLOAD_FOLDER, download_sessions
from request_logger import log_request

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

    # Capture request data before starting background thread
    def get_client_ip():
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr
    
    request_data = {
        'ip_address': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'referer': request.headers.get('Referer', ''),
        'is_extension': request.headers.get('X-Extension-Request') == 'true',
        'extension_version': request.headers.get('X-Extension-Version', ''),
        'platform': request.headers.get('X-Platform', ''),
        'language': request.headers.get('X-Language', '')
    }

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
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage'],
                    }
                },
                'format_sort': ['res', 'ext:mp4:m4a'],
                'format_sort_force': True,
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
                # Extract info first to log requests, then download
                for url in urls:
                    try:
                        info = ydl.extract_info(url, download=False)
                        # Log the request with captured request data
                        try:
                            log_request(url, info, format_type, 'download', request_data=request_data)
                        except Exception as log_err:
                            print(f"Error in log_request: {log_err}")
                            import traceback
                            traceback.print_exc()
                    except Exception as e:
                        print(f"Error extracting info for {url}: {e}")
                        # Try to log even if extraction fails
                        try:
                            log_request(url, None, format_type, 'download', request_data=request_data)
                        except Exception as log_err:
                            print(f"Error logging failed request: {log_err}")
                
                # Download all URLs
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
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage'],
                }
            },
            'format_sort': ['res', 'ext:mp4:m4a'],
            'format_sort_force': True,
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


@api_bp.route('/direct-links', methods=['GET'])
def direct_links_view():
    """Render the direct links view page"""
    return render_template('direct_links.html')


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

    # Try to extract info first for logging (even if it fails later)
    info = None
    extraction_error = None
    
    try:
        # Try multiple configurations to handle YouTube's changing system
        # Prefer formats that are more likely to be direct downloads (not m3u8)
        configs = [
            {
                'quiet': True,
                'skip_download': True,
                'cookiefile': 'app/cookies.txt',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web', 'ios'],
                        'player_skip': ['webpage'],
                    }
                },
                # Prefer formats with http/https protocol (direct downloads) over m3u8
                'format_sort': ['+protocol:http', '+protocol:https', 'res', 'ext:mp4:m4a'],
                'format_sort_force': True,
                'no_warnings': False,
            },
            {
                'quiet': True,
                'skip_download': True,
                'cookiefile': 'app/cookies.txt',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android'],
                    }
                },
            },
            {
                'quiet': True,
                'skip_download': True,
                'cookiefile': 'app/cookies.txt',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        ]
        
        for i, ydl_opts in enumerate(configs):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    # Log the request immediately after successful extraction
                    log_request(url, info, format_type, 'direct-links')
                    break  # If successful, break out of the loop
            except Exception as e:
                extraction_error = str(e)
                if i == len(configs) - 1:  # If this is the last config
                    # Try to log even if extraction failed
                    try:
                        # Try one more time with minimal config just to get basic info
                        minimal_config = {
                            'quiet': True,
                            'skip_download': True,
                        }
                        with yt_dlp.YoutubeDL(minimal_config) as ydl:
                            try:
                                info = ydl.extract_info(url, download=False)
                                log_request(url, info, format_type, 'direct-links')
                            except:
                                # If still fails, log with minimal info
                                log_request(url, None, format_type, 'direct-links')
                    except:
                        # Log with no info if all extraction attempts fail
                        log_request(url, None, format_type, 'direct-links')
                    raise e
                continue  # Try next config

        if info is None:
            return jsonify({"success": False, "error": "Could not extract video information with any configuration"}), 500

        grouped_links = defaultdict(list)
        v_info = defaultdict(list)

        def extract_urls(info_dict):
            formats = info_dict.get('formats', [])
            print(f"DEBUG: Total formats found: {len(formats)}")
            
            # Count formats before and after filtering for debugging
            total_before_filter = 0
            m3u8_count = 0
            valid_count = 0
            
            for i, fmt in enumerate(formats):
                ext = fmt.get('ext')
                url_ = fmt.get('url')
                protocol = fmt.get('protocol', '').lower()
                
                if not url_ or not ext:
                    continue
                
                total_before_filter += 1
                print(f"DEBUG FORMAT {i}: ext={ext}, vcodec={fmt.get('vcodec')}, acodec={fmt.get('acodec')}, format_id={fmt.get('format_id')}, resolution={fmt.get('resolution')}, protocol={protocol}")
                
                # Filter out m3u8/HLS formats - these are streaming playlists, not direct download links
                # Only filter if it's clearly an m3u8 file, not DASH segments which can be direct downloads
                url_lower = url_.lower()
                is_m3u8 = (
                    '.m3u8' in url_lower or 
                    ext.lower() == 'm3u8' or 
                    protocol in ['m3u8', 'm3u8_native'] or
                    'index.m3u8' in url_lower or
                    url_lower.endswith('.m3u8')
                )
                
                if is_m3u8:
                    m3u8_count += 1
                    print(f"DEBUG: Skipping m3u8/HLS format: format_id={fmt.get('format_id')}, protocol={protocol}, ext={ext}")
                    continue

                # Filtering by format type
                if format_type == 'video':
                    # For video, we'll be more flexible and include formats that might work
                    # Skip pure audio formats
                    if fmt.get('vcodec') == 'none':
                        continue
                    # Accept common video formats (mp4, webm, mkv) and also include formats without audio
                    if ext not in ['mp4', 'webm', 'mkv', '3gp', 'flv']:
                        continue
                else:  # audio
                    # For audio, skip video-only formats (no audio)
                    if fmt.get('acodec') == 'none':
                        continue
                    # Debug: Print all audio formats to see what's available
                    print(f"DEBUG AUDIO: ext={ext}, vcodec={fmt.get('vcodec')}, acodec={fmt.get('acodec')}, format_id={fmt.get('format_id')}")
                    # Accept only pure audio formats (not video+audio combinations)
                    if ext not in ['mp3', 'm4a', 'webm', 'aac', 'opus']:
                        continue
                    # Skip formats that have video codec (video+audio combinations)
                    if fmt.get('vcodec') != 'none':
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
                # link_info['ff'] = formats
                if fmt.get('vcodec') != 'none' and fmt.get('acodec') == 'none':
                    link_info['note'] = 'Video Only (No Audio)'

                valid_count += 1
                grouped_links[ext].append(link_info)
            
            print(f"DEBUG SUMMARY: Total formats={total_before_filter}, M3U8 filtered={m3u8_count}, Valid formats={valid_count}")
            
            if valid_count == 0 and total_before_filter > 0:
                print(f"WARNING: All {total_before_filter} formats were filtered out (all were m3u8)")

        # Extract URLs from the successfully obtained info
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
            # Check if we have formats but they were all filtered
            total_formats = len(info.get('formats', []))
            if total_formats > 0:
                return jsonify({
                    "success": False, 
                    "error": "No direct download formats available. YouTube may only be providing streaming (m3u8) formats for this video. Please use the main downloader instead."
                }), 404
            else:
                return jsonify({"success": False, "error": "No matching formats found"}), 404

        return jsonify({
            "success": True,
            "info": v_info,
            "links": grouped_links,
        })


    except Exception as e:
        # Log the request even if there's an error (if not already logged)
        if info is None:
            try:
                log_request(url, None, format_type, 'direct-links')
            except:
                pass
        return jsonify({"success": False, "error": str(e)}), 500

