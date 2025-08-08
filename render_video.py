import json, os, time, subprocess
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from synth_audio import synth_to_wav

TEMPLATE_DIR = "templates"
OUT_DIR = "output/queue"

def render_html_for_reply(q):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tmpl = env.get_template("robot_template.html")
    html = tmpl.render(comment=q['comment'], reply=q['reply_text'], tone="satirical")
    p = Path(OUT_DIR) / q['id']
    p.mkdir(parents=True, exist_ok=True)
    html_path = p / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path, p

def capture_frames(html_path, out_folder, frame_count=18, fps=12):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=800,600")
    options.add_argument("--hide-scrollbars")
    driver = webdriver.Chrome(options=options)
    try:
        url = f"file://{html_path.resolve()}"
        driver.get(url)
        time.sleep(0.6)
        for i in range(frame_count):
            driver.execute_script("window.advanceFrame && window.advanceFrame();")
            time.sleep(1.0/frame_count*1.2)
            out_img = Path(out_folder) / f"frame_{i:03d}.png"
            driver.save_screenshot(str(out_img))
    finally:
        driver.quit()

def combine_audio_frames(folder, audio_path, out_video_path, fps=12):
    frame_pattern = str(Path(folder)/"frame_%03d.png")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", frame_pattern,
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out_video_path)
    ]
    print("Running ffmpeg:", " ".join(cmd))
    subprocess.check_call(cmd)

def build_video_for_queue_item(qpath):
    with open(qpath, encoding='utf-8') as f:
        q = json.load(f)
    html_path, out_folder = render_html_for_reply(q)
    wav_path = Path(out_folder) / "reply.wav"
    synth_to_wav(q['reply_text'], wav_path)
    capture_frames(html_path, out_folder)
    mp4_out = Path(out_folder) / f"{q['id']}.mp4"
    combine_audio_frames(out_folder, wav_path, mp4_out)
    with open(Path(qpath).parent / f"{q['id']}.meta.json", "w", encoding='utf-8') as f:
        json.dump({"video": str(mp4_out), "wav": str(wav_path), "reply": q['reply_text']}, f, indent=2)
    return mp4_out

if __name__ == "__main__":
    import glob
    for p in glob.glob("output/queue/*.json"):
        print("Rendering", p)
        build_video_for_queue_item(p)
