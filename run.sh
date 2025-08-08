#!/usr/bin/env bash
set -e
echo "Run scraper -> generate replies -> render -> server"
python scrape.py
python generate_reply.py
python render_video.py
echo "Start moderation UI at http://localhost:5004"
python server.py
