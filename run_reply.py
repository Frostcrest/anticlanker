# run_reply.py
import os, sys, subprocess
from pathlib import Path
import time
from common import sha256, queue_dir

def run_py(script, *args):
    cmd = [sys.executable, script, *args]
    subprocess.check_call(cmd)

def open_file(path: Path):
    try:
        if os.name == "nt":
            os.startfile(str(path))  # Windows
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_reply.py \"<comment text>\" [<source_url>] [--headless true|false]")
        sys.exit(1)

    comment = sys.argv[1]
    source = "manual://run_reply"
    headless = os.getenv("HEADLESS", "false").lower()  # default headful
    args = sys.argv[2:]

    if args and not args[0].startswith("--"):
        source = args[0]
        args = args[1:]

    # parse flags
    i = 0
    while i < len(args):
        if args[i] == "--headless" and i + 1 < len(args):
            headless = str(args[i+1]).lower()
            i += 2
        else:
            i += 1

    # Set HEADLESS env for this run only
    env_headless = "true" if headless in ("1","true","yes") else "false"
    os.environ["HEADLESS"] = env_headless

    print(f"=> HEADLESS={env_headless}")
    print("=> Enqueueing…")
    run_py("enqueue_comment.py", comment, source)

    print("=> Generating reply…")
    run_py("generate_reply.py")

    print("=> Rendering video…")
    run_py("render_video.py")

    # Locate output and open it
    h = sha256(comment)
    mp4 = queue_dir() / h / f"{h}.mp4"
    if mp4.exists() and mp4.stat().st_size > 0:
        print(f"✅ Done. {mp4}")
        # auto-open
        open_file(mp4)
    else:
        print("⚠️ Render finished but video file not found. Check logs from render_video.py.")
        # show hints
        print("Check for files:")
        for p in [
            Path("output/queue") / f"{h}.json",
            Path("output/queue") / h / "reply.wav",
            Path("output/queue") / h / "frame_000.png",
        ]:
            print(" -", p, "exists?" , p.exists())

if __name__ == "__main__":
    main()
