import time
import os
import threading
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from api_routes import api_bp
from downloader_global import DOWNLOAD_FOLDER
from web_routes import web_bp

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
app.secret_key = 'your-secret-key'

app.register_blueprint(web_bp)
app.register_blueprint(api_bp)

@app.route('/downloads/<filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    else:
        return "File not found", 404

def auto_delete_old_files():
    print("[Auto Cleanup] Started.")
    while True:
        now = time.time()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)

            if not os.path.isfile(file_path):
                continue

            try:
                file_age = now - os.path.getmtime(file_path)

                # Skip if file is modified in the last 15 minutes
                if file_age < 900:
                    continue

                # Skip if file is currently in use (size still changing)
                size1 = os.path.getsize(file_path)
                time.sleep(1)
                size2 = os.path.getsize(file_path)

                if size1 != size2:
                    print(f"[Auto Cleanup] Skipping {filename}: still being written.")
                    continue

                # Safe to delete
                os.remove(file_path)
                print(f"[Auto Cleanup] Deleted: {filename} (age: {int(file_age)}s)")

            except Exception as e:
                print(f"[Auto Cleanup] Error deleting {filename}: {e}")

            time.sleep(300)  # check every 5 minutes


@app.route('/delete-server-downloaded-file')
def delete_old_files():
    print("[Auto Cleanup] Started.")
    now = time.time()
    deleted_files = []

    for filename in os.listdir(DOWNLOAD_FOLDER):
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

        if not os.path.isfile(file_path):
            continue

        try:
            file_age = now - os.path.getmtime(file_path)

            # Skip if file is modified in the last 10 minutes
            if file_age < 600:
                continue

            # Skip if file is still being written
            size1 = os.path.getsize(file_path)
            time.sleep(1)
            size2 = os.path.getsize(file_path)

            if size1 != size2:
                print(f"[Auto Cleanup] Skipping {filename}: still being written.")
                continue

            os.remove(file_path)
            print(f"[Auto Cleanup] Deleted: {filename} (age: {int(file_age)}s)")
            deleted_files.append(filename)

        except Exception as e:
            print(f"[Auto Cleanup] Error deleting {filename}: {e}")

    return jsonify({
        "success": True,
        "deleted_files": deleted_files
    })


def clear_all_downloaded_videos():
    """Clear all downloaded video files (but keep logs)"""
    try:
        if not os.path.exists(DOWNLOAD_FOLDER):
            print("[Daily Cleanup] Download folder does not exist.")
            return
        
        deleted_count = 0
        deleted_size = 0
        
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            
            if not os.path.isfile(file_path):
                continue
            
            try:
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                deleted_count += 1
                deleted_size += file_size
                print(f"[Daily Cleanup] Deleted: {filename}")
            except Exception as e:
                print(f"[Daily Cleanup] Error deleting {filename}: {e}")
        
        if deleted_count > 0:
            size_mb = round(deleted_size / (1024 * 1024), 2)
            print(f"[Daily Cleanup] Completed: Deleted {deleted_count} file(s), {size_mb} MB freed")
        else:
            print("[Daily Cleanup] No files to delete.")
            
    except Exception as e:
        print(f"[Daily Cleanup] Error in daily cleanup: {e}")
        import traceback
        traceback.print_exc()

def schedule_daily_cleanup():
    """Schedule daily cleanup at 12 AM (midnight) Bangladesh time"""
    import pytz
    
    bd_timezone = pytz.timezone('Asia/Dhaka')
    
    def run_at_midnight():
        while True:
            try:
                # Get current time in BD timezone
                now_bd = datetime.now(bd_timezone)
                
                # Calculate next midnight (12:00 AM) in BD timezone
                if now_bd.hour >= 0:
                    # If it's already past midnight, schedule for tomorrow
                    next_midnight = (now_bd + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    # Schedule for today's midnight
                    next_midnight = now_bd.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Calculate seconds until next midnight
                seconds_until_midnight = (next_midnight - now_bd).total_seconds()
                
                print(f"[Daily Cleanup] Next cleanup scheduled at: {next_midnight.strftime('%Y-%m-%d %H:%M:%S')} (BD Time)")
                print(f"[Daily Cleanup] Waiting {int(seconds_until_midnight / 3600)} hours and {int((seconds_until_midnight % 3600) / 60)} minutes...")
                
                # Sleep until midnight
                time.sleep(seconds_until_midnight)
                
                # Run cleanup at midnight
                print(f"[Daily Cleanup] Starting scheduled cleanup at {datetime.now(bd_timezone).strftime('%Y-%m-%d %H:%M:%S')} (BD Time)")
                clear_all_downloaded_videos()
                
            except Exception as e:
                print(f"[Daily Cleanup] Error in scheduler: {e}")
                import traceback
                traceback.print_exc()
                # If error occurs, wait 1 hour before retrying
                time.sleep(3600)
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_at_midnight, daemon=True)
    scheduler_thread.start()
    print("[Daily Cleanup] Daily cleanup scheduler started. Will run at 12:00 AM (BD Time) every day.")

# threading.Thread(target=auto_delete_old_files, daemon=True).start()

# Start daily cleanup scheduler
schedule_daily_cleanup()

if __name__ == '__main__':
    app.run(debug=True)
