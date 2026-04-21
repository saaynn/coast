#!/usr/bin/env bash

# Upgrade pip and install strict libraries
python -m pip install --upgrade pip
pip install PyNaCl==1.5.0 --only-binary :all:
pip install -r requirements.txt

# Force the newest youtube bypasses
pip install --upgrade yt-dlp

# Download, extract, and UNLOCK FFmpeg
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg-release-amd64-static.tar.xz
mv ffmpeg-*-static/ffmpeg .
mv ffmpeg-*-static/ffprobe .
rm -rf ffmpeg-*-static*

# THIS IS THE MAGIC UNLOCK LINE:
chmod +x ffmpeg ffprobe
