# TikTok Robo-Slur AI Responder - Prototype (Free Tools MVP)

This repository is a vibe-coded proof-of-concept that:
- Scrapes TikTok comments for "robo-slur" terms (e.g., clanker, bolt eater, wireback) using Selenium.
- Generates short contextual replies (LLM optional, fallback templates included).
- Synthesizes voice with `pyttsx3` and renders a simple robot avatar video using headless Chrome screenshots and `ffmpeg`.
- Provides a local moderation UI for reviewing generated reply videos before manual posting to TikTok.

**Important**: This repo uses only free tools for the prototype. Automatic posting to TikTok is intentionally omitted to avoid TOS issues — you must manually review and post generated videos.

## Quickstart

Prerequisites:
- Python 3.10+
- Google Chrome/Chromium installed
- Chromedriver (or rely on Selenium Manager)
- ffmpeg installed and on PATH

1. Create and activate a virtualenv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Edit `config.yaml` with at least one TikTok video URL.
3. Run the scraper once:
   ```bash
   python scrape.py
   ```
4. Generate replies:
   ```bash
   python generate_reply.py
   ```
5. Render videos:
   ```bash
   python render_video.py
   ```
6. Review in the moderation UI:
   ```bash
   python server.py
   ```
   Open: http://localhost:5004

## Files of interest
- `scrape.py` - Selenium-based comment ingestion and detection.
- `generate_reply.py` - Builds the textual reply (LLM optional).
- `synth_audio.py` - TTS via pyttsx3.
- `render_video.py` - Renders HTML/SVG frames and combines audio into MP4 via ffmpeg.
- `templates/robot_template.html` - Robot avatar template (Jinja2).
- `server.py` - Simple Flask moderation UI.

## License
MIT
