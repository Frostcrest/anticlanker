"""
Common utilities for the anticlanker project.

Centralizes:
- Config loading (config.yaml)
- Output/queue/published directories
- Logging setup
- Text hashing
- Chrome WebDriver creation
- ffmpeg binary resolution
"""
from __future__ import annotations

from pathlib import Path
import json
import logging
import os
import hashlib
from typing import Any, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    """Load YAML config with safe defaults. Returns {} if missing/invalid."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def output_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    return (REPO_ROOT / Path(cfg.get("output_dir", "./output"))).resolve()


def queue_dir(cfg: dict | None = None) -> Path:
    return output_dir(cfg) / "queue"


def published_dir(cfg: dict | None = None) -> Path:
    return output_dir(cfg) / "published"


def ensure_dirs(cfg: dict | None = None) -> None:
    q = queue_dir(cfg)
    p = published_dir(cfg)
    q.mkdir(parents=True, exist_ok=True)
    p.mkdir(parents=True, exist_ok=True)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Create a console logger. Level can be overridden by LOG_LEVEL env."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    lvl = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logger.setLevel(getattr(logging, lvl, logging.INFO))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(ch)
    return logger


def resolve_headless(default: bool = False) -> bool:
    val = os.getenv("HEADLESS", None)
    if val is None:
        return default
    return str(val).lower() in ("1", "true", "yes")


def get_chrome_driver(headless: Optional[bool] = None, window_size: str = "1280,900") -> webdriver.Chrome:
    """Return a configured Chrome WebDriver. Uses webdriver-manager.

    Respects env:
      - HEADLESS: true/false
      - CHROME_USER_DATA_DIR: path to user data dir
      - CHROME_PROFILE_DIR: profile directory name (e.g., "Default")
    """
    headless = resolve_headless() if headless is None else headless
    opts = Options()
    if headless:
        # Modern headless; keep software renderer to avoid GL issues on CI
        opts.add_argument("--headless=new")
        opts.add_argument("--enable-unsafe-swiftshader")
        opts.add_argument("--use-gl=swiftshader")
        opts.add_argument("--disable-gpu")
    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--lang=en-US")
    opts.add_argument("--disable-blink-features=AutomationControlled")

    # Optional profile reuse (helps with sites requiring login)
    user_data = os.getenv("CHROME_USER_DATA_DIR")
    profile_dir = os.getenv("CHROME_PROFILE_DIR")
    if user_data:
        opts.add_argument(f"--user-data-dir={user_data}")
    if profile_dir:
        opts.add_argument(f"--profile-directory={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(90)
    return driver


def ffmpeg_bin() -> str:
    return os.getenv("FFMPEG_BIN", "ffmpeg")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
