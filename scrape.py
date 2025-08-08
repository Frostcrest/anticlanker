# scrape.py
import os
import re
import json
import time
import yaml
from pathlib import Path
from datetime import datetime, timezone

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

CONFIG_PATH = "config.yaml"
STATE_FILE = "output/seen_comments.json"


# ---------- Config / FS helpers ----------
def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs(cfg):
    out = Path(cfg["output_dir"])
    (out / "queue").mkdir(parents=True, exist_ok=True)
    (out / "published").mkdir(parents=True, exist_ok=True)


def load_seen():
    p = Path(STATE_FILE)
    if not p.exists():
        return set()
    with p.open("r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen(seen):
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, indent=2)


def hash_text(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------- WebDriver ----------
def get_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    # HEADFUL (comment out the next line)
    # opts.add_argument("--headless=new")

    # Window big enough for TikTok layout
    opts.add_argument("--window-size=1280,2000")

    # Keep GPU ON in headful; it’s more stable for WebGL
    # opts.add_argument("--disable-gpu")  # <— leave this commented in headful

    # Anti-automation noise reducers
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=en-US")
    opts.add_argument("--mute-audio")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

    # Optional: reuse your Chrome profile (often helps TikTok render)
    # opts.add_argument(r"--user-data-dir=C:\Users\<YOU>\AppData\Local\Google\Chrome\User Data")
    # opts.add_argument("--profile-directory=Default")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
    except Exception:
        pass

    driver.set_page_load_timeout(60)
    return driver

# ---------- Scraping ----------
def _accept_cookies_if_present(driver):
    # Try a few generic consent button texts
    labels = ["Accept", "I agree", "Agree", "Accept all", "Allow all"]
    for label in labels:
        try:
            btns = driver.find_elements(By.XPATH, f"//button[contains(.,'{label}')]")
            if btns:
                btns[0].click()
                time.sleep(0.8)
                return True
        except Exception:
            pass
    return False


def _scroll_to_load_comments(driver, rounds=6, px=800, delay=0.8):
    for _ in range(rounds):
        driver.execute_script(f"window.scrollBy(0, {px});")
        time.sleep(delay)


def _click_show_more_if_present(driver, attempts=3):
    for _ in range(attempts):
        try:
            more = driver.find_elements(
                By.XPATH,
                "//button[contains(.,'More comments') or contains(.,'Show more')]"
            )
            if more:
                more[0].click()
                time.sleep(1.0)
            else:
                break
        except Exception:
            break


def find_comments_on_page(driver, url):
    driver.get(url)
    time.sleep(3)  # initial settle

    _accept_cookies_if_present(driver)
    _scroll_to_load_comments(driver, rounds=6)
    _click_show_more_if_present(driver, attempts=3)

    # Multiple fallback selectors because TikTok DOM changes often
    selectors = [
        "//div[contains(@data-e2e,'comment-item')]//*[self::p or self::span]",
        "//div[contains(@class,'comment-item') or contains(@class,'CommentItem')]//*[self::p or self::span]",
        "//p[contains(@class,'comment') or contains(@class,'Comment') or contains(@class,'text')]",
    ]

    elements = []
    for sel in selectors:
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, sel)))
            els = driver.find_elements(By.XPATH, sel)
            elements.extend(els)
        except TimeoutException:
            continue

    if not elements:
        # Last resort: any p with content
        ps = driver.find_elements(By.TAG_NAME, "p")
        elements = [p for p in ps if len(p.text.strip()) > 2][:200]

    now_iso = datetime.now(timezone.utc).isoformat()
    seen_texts = set()
    comments = []

    for el in elements:
        txt = el.text.strip()
        if not txt or len(txt) < 3:
            continue
        # Filter obvious UI noise (you can add more strings here)
        junk = (
            "Log in", "Sign up", "Download", "Open app", "Follow", "Share",
            "Copy link", "Add comment", "Reply", "Like"
        )
        if any(j in txt for j in junk):
            continue
        if txt in seen_texts:
            continue
        seen_texts.add(txt)
        comments.append({"text": txt, "scraped_at": now_iso})

    return comments


# ---------- Matching ----------
def matches_keyword(cfg, comment_text):
    text = comment_text.lower()
    for kw in cfg.get("keywords", []):
        if kw.lower() in text:
            return True, f"keyword:{kw}"
    for rx in cfg.get("regex_variations", []):
        try:
            if re.search(rx, comment_text):
                return True, f"regex:{rx}"
        except re.error as e:
            print(f"[regex error] {rx}: {e}")
    return False, None


# ---------- Main ----------
def main_once():
    cfg = load_config()
    ensure_dirs(cfg)
    seen = load_seen()
    driver = get_driver()

    try:
        for t in cfg.get("targets", []):
            url = t["url"]
            print("Scraping", url)
            try:
                comments = find_comments_on_page(driver, url)
            except WebDriverException as e:
                print(f"[driver error] {e}")
                continue

            for c in comments:
                h = hash_text(c["text"])
                if h in seen:
                    continue
                matched, pattern = matches_keyword(cfg, c["text"])
                if matched:
                    print("Matched:", c["text"], "| via", pattern)
                    out = {
                        "id": h,
                        "url": url,
                        "comment": c["text"],
                        "matched_pattern": str(pattern),
                        "timestamp": c["scraped_at"],
                    }
                    qpath = Path(cfg["output_dir"]) / "queue" / f"{h}.json"
                    with open(qpath, "w", encoding="utf-8") as f:
                        json.dump(out, f, indent=2, ensure_ascii=False)
                seen.add(h)

        save_seen(seen)

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main_once()
