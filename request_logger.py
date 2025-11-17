import json
import os
from datetime import datetime
from flask import request

LOG_FILE = 'request_logs.json'

def get_client_ip():
    """Get the client's IP address from the request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def log_request(video_url, video_info=None, format_type=None, request_type='download'):
    """
    Log a video request to JSON file
    
    Args:
        video_url: The video URL that was requested
        video_info: Dictionary containing video information from yt-dlp
        format_type: 'video' or 'audio'
        request_type: 'download' or 'direct-links'
    """
    try:
        # Load existing logs
        logs = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                logs = []
        
        # Prepare log entry
        log_entry = {
            'id': len(logs) + 1,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': get_client_ip(),
            'video_url': video_url,
            'request_type': request_type,
            'format_type': format_type,
            'video_info': {
                'title': video_info.get('title', 'Unknown') if video_info else 'Unknown',
                'platform': video_info.get('extractor_key', 'Unknown') if video_info else 'Unknown',
                'channel': video_info.get('channel', 'Unknown') if video_info else 'Unknown',
                'channel_id': video_info.get('channel_id', 'Unknown') if video_info else 'Unknown',
                'duration': video_info.get('duration_string', 'Unknown') if video_info else 'Unknown',
                'thumbnail': video_info.get('thumbnail', '') if video_info else '',
                'view_count': video_info.get('view_count', 0) if video_info else 0,
                'upload_date': video_info.get('upload_date', 'Unknown') if video_info else 'Unknown',
                'video_id': video_info.get('display_id', 'Unknown') if video_info else 'Unknown',
                'uploader': video_info.get('uploader', 'Unknown') if video_info else 'Unknown',
            }
        }
        
        # Add to logs
        logs.append(log_entry)
        
        # Keep only last 1000 entries to prevent file from growing too large
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        # Save to file
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error logging request: {e}")
        return False

