# scrape.py
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from common import load_config, ensure_dirs, queue_dir, sha256, get_chrome_driver

STATE_FILE = str((Path(__file__).parent / "output/seen_comments.json").resolve())


# ---------- Config / FS helpers ----------
def _load_cfg():
    return load_config() or {}


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
    return sha256(s)


# ---------- WebDriver ----------
def get_driver():
    driver = get_chrome_driver(headless=False, window_size="1280,2000")
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
    except Exception:
        pass
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
    cfg = _load_cfg()
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
                    qpath = queue_dir(cfg) / f"{h}.json"
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
