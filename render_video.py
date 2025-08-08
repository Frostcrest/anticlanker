# render_video.py
import json
import os
import time
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from synth_audio import synth_to_wav

TEMPLATE_DIR = "templates"
QUEUE_DIR = Path("output/queue")

# Default to headful for stability; you can set HEADLESS=true later
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("1", "true", "yes")
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")


def log(*args):
    print("[render]", *args, flush=True)


def get_driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
        # software GL stack for headless to avoid WebGL deprecations
        opts.add_argument("--enable-unsafe-swiftshader")
        opts.add_argument("--use-gl=swiftshader")
        opts.add_argument("--disable-gpu")
    # headful: keep GPU enabled
    opts.add_argument("--window-size=900,600")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--lang=en-US")
    # Quiet down some bot heuristics
    opts.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    # Hide webdriver flag a bit
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"}
        )
    except Exception:
        pass

    driver.set_page_load_timeout(60)
    return driver


def render_html_for_reply(q):
    tmpl_path = Path(TEMPLATE_DIR) / "robot_template.html"
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template missing: {tmpl_path}")

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tmpl = env.get_template("robot_template.html")
    html = tmpl.render(comment=q["comment"], reply=q["reply_text"], tone="satirical")

    out_folder = QUEUE_DIR / q["id"]
    out_folder.mkdir(parents=True, exist_ok=True)
    html_path = out_folder / "index.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path, out_folder


def wait_for_ready(driver):
    # document.readyState === 'complete'
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    # and robot SVG present
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".robot-svg"))
    )


def capture_frames(html_path: Path, out_folder: Path, frame_count=18, fps=12) -> int:
    driver = get_driver()
    try:
        url = html_path.resolve().as_uri()  # file:///C:/... (Windows-safe)
        log("Opening", url, f"(HEADLESS={HEADLESS})")
        driver.get(url)

        wait_for_ready(driver)
        # small settle time to ensure CSS applied
        time.sleep(0.5)

        if not HEADLESS:
            # Visual confirm (optional): uncomment to pause
            # input("[render] Headful: page should be visible. Press Enter to continue...")
            pass

        # First screenshot
        first = out_folder / "frame_000.png"
        ok = driver.get_screenshot_as_file(str(first))
        if not ok or not first.exists() or first.stat().st_size == 0:
            # Dump page HTML to inspect if blank
            dump = out_folder / "debug_page_dump.html"
            dump.write_text(driver.page_source, encoding="utf-8")
            log("First screenshot failed. Wrote HTML dump to", dump)
            return 0

        # Additional frames (advance the mouth animation hook if present)
        for i in range(1, frame_count):
            try:
                driver.execute_script("window.advanceFrame && window.advanceFrame();")
            except Exception:
                pass
            time.sleep(1.0 / max(fps, 1))
            driver.get_screenshot_as_file(str(out_folder / f"frame_{i:03d}.png"))

        n = len(list(out_folder.glob("frame_*.png")))
        log(f"Wrote {n} frames to {out_folder}")
        return n

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def combine_audio_frames(folder: Path, audio_path: Path, out_video_path: Path, fps=12):
    frame_pattern = str(folder / "frame_%03d.png")
    cmd = [
        FFMPEG_BIN, "-y",
        "-framerate", str(fps),
        "-i", frame_pattern,
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out_video_path),
    ]
    log("Running ffmpeg:", " ".join(cmd))
    subprocess.check_call(cmd)


def build_video_for_queue_item(qpath: Path):
    q = json.loads(Path(qpath).read_text(encoding="utf-8"))
    if "reply_text" not in q or not q["reply_text"].strip():
        log("Queue item missing reply_text, run generate_reply.py first:", qpath)
        return None

    html_path, out_folder = render_html_for_reply(q)

    wav_path = out_folder / "reply.wav"
    synth_to_wav(q["reply_text"], wav_path)
    if not wav_path.exists() or wav_path.stat().st_size == 0:
        log("ERROR: TTS failed; no WAV at", wav_path)
        return None

    frames = capture_frames(html_path, out_folder)
    if frames == 0:
        log("ERROR: No frames captured. See any debug_page_dump.html in", out_folder)
        return None

    mp4_out = out_folder / f"{q['id']}.mp4"
    try:
        combine_audio_frames(out_folder, wav_path, mp4_out)
    except FileNotFoundError:
        log("ERROR: ffmpeg not found. Set FFMPEG_BIN env var to full path (e.g., C:\\ffmpeg\\bin\\ffmpeg.exe).")
        return None

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
