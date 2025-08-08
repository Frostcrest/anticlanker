# selenium_sanity.py
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

p = Path("output/debug"); p.mkdir(parents=True, exist_ok=True)
html = p / "index.html"
html.write_text("<html><body style='background:#102030;color:#eef;font:20px system-ui'>Selenium headful test.</body></html>", encoding="utf-8")
url = html.resolve().as_uri()
print("URL:", url)

opts = Options()
opts.add_argument("--window-size=900,600")  # HEADFUL: do NOT add --headless
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

print("Opened Chrome OK. Navigating...")
driver.get(url)
time.sleep(1.5)
shot = p / "screen.png"
driver.save_screenshot(str(shot))
print("Screenshot exists?", shot.exists(), shot)
input("A Chrome window should be visible. Press Enter to close...")
driver.quit()
print("Closed.")
