import os

DOWNLOAD_FOLDER = 'static/downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_sessions = {}