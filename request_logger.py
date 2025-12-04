import json
import os
from datetime import datetime
from flask import request
import pytz

# Use absolute path for log file to ensure it's saved in the correct location
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'request_logs.json')

def get_client_ip():
    """Get the client's IP address from the request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def log_request(video_url, video_info=None, format_type=None, request_type='download', metadata=None, request_data=None):
    """
    Log a video request to JSON file
    
    Args:
        video_url: The video URL that was requested
        video_info: Dictionary containing video information from yt-dlp
        format_type: 'video' or 'audio'
        request_type: 'download' or 'direct-links'
        metadata: Optional dictionary with additional metadata (user_agent, browser, extension_version, etc.)
        request_data: Optional dictionary with request context data (ip_address, user_agent, headers, etc.)
                     If not provided, will try to get from Flask request context
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
        
        # Get request data - either from passed request_data or from Flask request context
        if request_data:
            ip_address = request_data.get('ip_address', 'Unknown')
            user_agent = request_data.get('user_agent', 'Unknown')
            referer = request_data.get('referer', '')
            is_extension = request_data.get('is_extension', False)
            extension_version = request_data.get('extension_version', '')
        else:
            # Try to get from Flask request context (only works in request context)
            try:
                ip_address = get_client_ip()
                user_agent = request.headers.get('User-Agent', 'Unknown')
                referer = request.headers.get('Referer', '')
                is_extension = request.headers.get('X-Extension-Request') == 'true' or 'extension' in user_agent.lower()
                extension_version = request.headers.get('X-Extension-Version', '')
            except RuntimeError:
                # Working outside request context - use defaults
                ip_address = 'Unknown'
                user_agent = 'Unknown'
                referer = ''
                is_extension = False
                extension_version = ''
        
        # Extract browser info from user agent
        browser_info = 'Unknown'
        if 'Chrome' in user_agent:
            browser_info = 'Chrome'
        elif 'Firefox' in user_agent:
            browser_info = 'Firefox'
        elif 'Safari' in user_agent:
            browser_info = 'Safari'
        elif 'Edge' in user_agent:
            browser_info = 'Edge'
        
        # Get Bangladesh timezone
        bd_timezone = pytz.timezone('Asia/Dhaka')
        bd_time = datetime.now(bd_timezone)
        
        # Prepare log entry
        log_entry = {
            'id': len(logs) + 1,
            'timestamp': bd_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': 'Asia/Dhaka (UTC+6)',
            'ip_address': ip_address,
            'video_url': video_url,
            'request_type': request_type,
            'format_type': format_type,
            'user_agent': user_agent,
            'browser': browser_info,
            'is_extension': is_extension,
            'extension_version': extension_version if is_extension else None,
            'referer': referer if referer else None,
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
        
        # Add custom metadata if provided
        if metadata:
            log_entry['metadata'] = metadata
        
        # Add to logs
        logs.append(log_entry)
        
        # Keep only last 1000 entries to prevent file from growing too large
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        # Save to file
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
            print(f"Successfully logged request: {video_url} (ID: {log_entry['id']})")
            return True
        except Exception as save_error:
            print(f"Error saving log file: {save_error}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
    except Exception as e:
        import traceback
        print(f"Error logging request: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        # Try to log to a separate error file if main logging fails
        try:
            error_log_file = 'request_logs_error.txt'
            bd_timezone = pytz.timezone('Asia/Dhaka')
            bd_time = datetime.now(bd_timezone)
            with open(error_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{bd_time.strftime('%Y-%m-%d %H:%M:%S')} (BD Time) - Error: {e}\n")
                f.write(f"Traceback: {traceback.format_exc()}\n")
                f.write(f"Video URL: {video_url}\n")
                f.write("---\n")
        except:
            pass
        return False

