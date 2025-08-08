# tiktok_uploader.py
import os, time, json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

UPLOAD_URL = "https://www.tiktok.com/upload?lang=en"

def get_driver(headless=False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--enable-unsafe-swiftshader")
        opts.add_argument("--use-gl=swiftshader")
        opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=en-US")
    opts.add_argument("--disable-blink-features=AutomationControlled")

    # Use your real Chrome profile so you’re logged in
    # >>>> CHANGE THIS TO YOUR PROFILE PATH <<<<
    # Example:
    # opts.add_argument(r"--user-data-dir=C:\Users\YOU\AppData\Local\Google\Chrome\User Data")
    # opts.add_argument("--profile-directory=Default")

    service = Service(ChromeDriverManager().install())
    d = webdriver.Chrome(service=service, options=opts)
    d.set_page_load_timeout(90)
    return d

def upload_video(video_path: Path, caption: str, headless=False):
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    d = get_driver(headless=headless)
    wait = WebDriverWait(d, 30)

    try:
        d.get(UPLOAD_URL)

        # You must be logged in already (profile reuse recommended).
        # Wait for upload input
        # TikTok changes DOM often; try multiple selectors
        candidates = [
            "//input[@type='file']",
            "//div[@role='button']//input[@type='file']",
            "//input[contains(@accept,'.mp4')]",
        ]

        file_input = None
        for sel in candidates:
            try:
                file_input = wait.until(EC.presence_of_element_located((By.XPATH, sel)))
                break
            except Exception:
                continue
        if file_input is None:
            raise RuntimeError("Could not find file input on upload page. Are you logged in? Different UI?")

        file_input.send_keys(str(video_path))
        time.sleep(2)

        # Caption box (try multiple selectors)
        cap = None
        for sel in [
            "//div[@role='textbox']",
            "//textarea",
            "//div[contains(@class,'public-DraftEditor-content')]",
        ]:
            try:
                cap = wait.until(EC.presence_of_element_located((By.XPATH, sel)))
                break
            except Exception:
                continue
        if cap:
            try:
                cap.click()
                time.sleep(0.5)
                cap.clear()  # may not work on contenteditable divs
            except Exception:
                pass
            cap.send_keys(caption[:150])  # TikTok caption limit varies; keep short

        print("\n✅ Video attached and caption filled.")
        print("👉 Review settings (cover, tags, visibility), then click POST manually.")
        input("Press Enter to close the browser when you're done…")

    finally:
        try: d.quit()
        except: pass

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Path to MP4")
    ap.add_argument("--caption", default="", help="Caption text")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    upload_video(Path(args.video), args.caption, headless=args.headless)
