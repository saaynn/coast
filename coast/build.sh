#!/usr/bin/env bash

# Install Python dependencies
pip install -r requirements.txt

pip install --upgrade yt-dlp

# Download the static build of FFmpeg for Linux
wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz

# Extract the archive
tar -xf ffmpeg-release-amd64-static.tar.xz

# Move the ffmpeg and ffprobe binaries to the root directory
mv ffmpeg-*-static/ffmpeg .
mv ffmpeg-*-static/ffprobe .

# Clean up the downloaded archive files
rm -rf ffmpeg-*-static*
