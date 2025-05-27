import time
import os
import threading
from flask import Flask, send_from_directory
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


# threading.Thread(target=auto_delete_old_files, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
