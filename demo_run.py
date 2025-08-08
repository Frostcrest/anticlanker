# demo_run.py
import subprocess
import sys
import json
from pathlib import Path
import hashlib

def run_py(script, *args):
    """Run a Python script with the SAME interpreter (venv-safe)."""
    cmd = [sys.executable, script, *args]
    subprocess.check_call(cmd)

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    if len(sys.argv) < 2:
        print("Usage: python demo_run.py \"<comment text>\" [<source_url>]")
        sys.exit(1)

    comment = sys.argv[1]
    source = sys.argv[2] if len(sys.argv) > 2 else "https://example.com/manual"
    cid = sha256(comment)

    print("=> Enqueueing…")
    run_py("enqueue_comment.py", comment, source)

    print("=> Generating reply…")
    run_py("generate_reply.py")

    print("=> Rendering video…")
    run_py("render_video.py")

    mp4 = Path("output/queue") / cid / f"{cid}.mp4"
    if mp4.exists():
        print(f"✅ Done. Video at: {mp4}")
    else:
        print("⚠️ Render finished but video file not found. Check logs from render_video.py.")

if __name__ == "__main__":
    main()
