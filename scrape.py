import time, yaml, json, os, re, hashlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from datetime import datetime
from pathlib import Path

CONFIG_PATH = "config.yaml"
STATE_FILE = "output/seen_comments.json"

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def ensure_dirs(cfg):
    Path(cfg['output_dir']).mkdir(parents=True, exist_ok=True)
    Path(cfg['output_dir']) . joinpath('queue').mkdir(parents=True, exist_ok=True)
    Path(cfg['output_dir']) . joinpath('published').mkdir(parents=True, exist_ok=True)

def hash_text(s):
    import hashlib
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1200,2000")
    driver = webdriver.Chrome(options=options)
    return driver

def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE) as f:
        data = json.load(f)
    return set(data)

def save_seen(s):
    with open(STATE_FILE, "w") as f:
        json.dump(list(s), f, indent=2)

def find_comments_on_page(driver, url):
    driver.get(url)
    time.sleep(4)
    comments = []
    comment_selectors = [
        "//div[contains(@data-e2e,'comment-item')]",
        "//div[contains(@class,'comment-item') or contains(@class,'CommentItem')]",
        "//p[contains(@class,'comment-text')]"
    ]
    elements = []
    for sel in comment_selectors:
        try:
            els = driver.find_elements(By.XPATH, sel)
            elements.extend(els)
        except Exception:
            pass
    if not elements:
        ps = driver.find_elements(By.TAG_NAME, "p")
        elements = [p for p in ps if len(p.text.strip())>2][:100]

    for el in elements:
        text = el.text.strip()
        if not text:
            continue
        comments.append({
            "text": text,
            "scraped_at": datetime.utcnow().isoformat()
        })
    return comments

def matches_keyword(cfg, comment_text):
    text = comment_text.lower()
    for kw in cfg['keywords']:
        if kw.lower() in text:
            return True, kw
    for rx in cfg.get('regex_variations', []):
        if re.search(rx, comment_text):
            return True, rx
    return False, None

def main_once():
    cfg = load_config()
    ensure_dirs(cfg)
    seen = load_seen()
    driver = get_driver()
    try:
        for t in cfg['targets']:
            url = t['url']
            print("Scraping", url)
            comments = find_comments_on_page(driver, url)
            for c in comments:
                h = hash_text(c['text'])
                if h in seen:
                    continue
                matched, pattern = matches_keyword(cfg, c['text'])
                if matched:
                    print("Matched:", c['text'])
                    out = {
                        "id": h,
                        "url": url,
                        "comment": c['text'],
                        "matched_pattern": str(pattern),
                        "timestamp": c['scraped_at']
                    }
                    qpath = Path(cfg['output_dir']) / 'queue' / f"{h}.json"
                    with open(qpath, "w", encoding="utf-8") as f:
                        json.dump(out, f, indent=2, ensure_ascii=False)
                seen.add(h)
        save_seen(seen)
    finally:
        driver.quit()

if __name__ == "__main__":
    main_once()
