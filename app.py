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
    while True:
        now = time.time()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > 600:
                age = now - os.path.getmtime(file_path)
                print(f"{filename} age: {age} seconds")

                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
        time.sleep(60)


threading.Thread(target=auto_delete_old_files, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
