import time

from flask import Flask, render_template, request, send_from_directory, jsonify
import yt_dlp
import os
import threading

app = Flask(__name__)

DOWNLOAD_FOLDER = 'static/downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Global variables
download_progress = {
    "percent": "0%",
    "status": "Idle",
    "filename": None
}


@app.route('/')
def index():
    return render_template('index.html', status=download_progress['status'], error=None)


@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    format_type = request.form.get('format')

    if not url:
        return render_template('index.html', error="Please enter a valid YouTube URL.", status=download_progress['status'])

    def progress_hook(d):
        if d['status'] == 'downloading':
            download_progress['percent'] = d.get('_percent_str', '0.0%').strip()
            download_progress['status'] = "Downloading"
        elif d['status'] == 'finished':
            download_progress['percent'] = "100%"
            download_progress['status'] = "Processing..."

    def download():
        try:
            timestamp = int(time.time())  # Generate unique suffix
            ext = 'mp3' if format_type == 'audio' else 'mp4'
            generated_name = f'ytdl_{timestamp}'  # e.g., ytdl_1714892991
            output_template = os.path.join(DOWNLOAD_FOLDER, f"{generated_name}.%(ext)s")

            ydl_opts = {
                'progress_hooks': [progress_hook],
                'outtmpl': output_template,
                'cookies': '/app/cookies.txt',
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
            else:
                ydl_opts.update({'format': 'best'})

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)

            # Save the final file name after yt_dlp processes it
            download_progress['filename'] = f"{generated_name}.{ext}"
            download_progress['status'] = "Completed"

        except Exception as e:
            download_progress['status'] = f"Error: {str(e)}"
            download_progress['filename'] = None

    download_progress['status'] = "Downloading"
    download_progress['percent'] = "0%"
    download_progress['filename'] = None
    threading.Thread(target=download, daemon=True).start()

    return render_template('index.html', status=download_progress['status'], error=None)


@app.route('/progress')
def get_progress():
    return jsonify(download_progress)


@app.route('/downloads/<filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)
    else:
        return "File not found", 404


if __name__ == '__main__':
    app.run(debug=True)
