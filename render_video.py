# render_video.py
import json, os, time, subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from synth_audio import synth_to_wav
from audio_envelope import audio_to_envelope
from common import get_chrome_driver, ffmpeg_bin, queue_dir, get_logger

TEMPLATE_DIR = "templates"
QUEUE_DIR = queue_dir()
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("1","true","yes")
FFMPEG_BIN = ffmpeg_bin()
FPS = 12
FRAME_COUNT = 72  # ~6s @ 12fps; bump for longer clips

logger = get_logger("render")

def log(*a):
    logger.info(" ".join(str(x) for x in a))

def get_driver():
    # Delegate to common for consistent setup
    return get_chrome_driver(headless=HEADLESS, window_size="900,600")

def render_html_for_reply(q, amps):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tmpl = env.get_template("robot_template.html")
    # inject a script tag that sets window._injectedAmps
    inj = f"<script>var _injectedAmps = {json.dumps(amps)};</script>"
    html = tmpl.render(comment=q["comment"], reply=q["reply_text"], tone="satirical")
    html = html.replace("</body>", inj + "\n</body>")

    out_folder = QUEUE_DIR / q["id"]
    out_folder.mkdir(parents=True, exist_ok=True)
    html_path = out_folder / "index.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path, out_folder

def wait_ready(driver):
    WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".robot-svg")))

def capture_frames(html_path: Path, out_folder: Path, frame_count=FRAME_COUNT, fps=FPS) -> int:
    driver = get_driver()
    try:
        url = html_path.resolve().as_uri()
        log("Opening", url, f"(HEADLESS={HEADLESS})")
        driver.get(url)
        wait_ready(driver)
        time.sleep(0.5)

        # First frame
        first = out_folder / "frame_000.png"
        ok = driver.get_screenshot_as_file(str(first))
        if not ok or not first.exists() or first.stat().st_size == 0:
            (out_folder / "debug_page_dump.html").write_text(driver.page_source, encoding="utf-8")
            log("First screenshot failed; wrote HTML dump.")
            return 0

        # Remaining frames
        for i in range(1, frame_count):
            try:
                driver.execute_script("window.advanceFrame && window.advanceFrame();")
            except Exception:
                pass
            time.sleep(1.0 / max(fps,1))
            driver.get_screenshot_as_file(str(out_folder / f"frame_{i:03d}.png"))

        n = len(list(out_folder.glob("frame_*.png")))
        log(f"Wrote {n} frames to {out_folder}")
        return n
    finally:
        try: driver.quit()
        except: pass

def combine(out_folder: Path, audio_path: Path, out_video_path: Path, fps=FPS):
    pattern = str(out_folder / "frame_%03d.png")
    cmd = [FFMPEG_BIN, "-y", "-framerate", str(fps), "-i", pattern,
           "-i", str(audio_path), "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", str(out_video_path)]
    log("Running ffmpeg:", " ".join(cmd))
    subprocess.check_call(cmd)

def build_video_for_queue_item(qpath: Path):
    q = json.loads(qpath.read_text(encoding="utf-8"))
    if "reply_text" not in q or not q["reply_text"].strip():
        log("Queue item missing reply_text; run generate_reply.py first:", qpath)
        return None

    out_folder = QUEUE_DIR / q["id"]
    wav_path = out_folder / "reply.wav"
    synth_to_wav(q["reply_text"], wav_path)
    if not wav_path.exists() or wav_path.stat().st_size == 0:
        log("ERROR: TTS failed; no WAV at", wav_path)
        return None

    # Compute mouth amplitudes from audio
    amps = audio_to_envelope(wav_path, n_frames=FRAME_COUNT, fps=FPS, floor=0.2, ceil=1.0)

    html_path, out_folder = render_html_for_reply(q, amps)
    frames = capture_frames(html_path, out_folder)
    if frames == 0:
        log("ERROR: No frames captured.")
        return None

    mp4_out = out_folder / f"{q['id']}.mp4"
    combine(out_folder, wav_path, mp4_out)
    (out_folder / f"{q['id']}.meta.json").write_text(
        json.dumps({"video": str(mp4_out), "wav": str(wav_path), "reply": q["reply_text"]}, indent=2),
        encoding="utf-8"
    )
    log("Video created:", mp4_out)
    return mp4_out

if __name__ == "__main__":
    import glob
    log(f"HEADLESS={HEADLESS}, FFMPEG_BIN={FFMPEG_BIN}")
    qfiles = glob.glob(str(QUEUE_DIR / "*.json"))
    if not qfiles:
        log("No queue items found in", QUEUE_DIR)
    for p in qfiles:
        log("Rendering", p)
        build_video_for_queue_item(Path(p))
