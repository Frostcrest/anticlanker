# enqueue_comment.py
import json, sys, hashlib, time
from pathlib import Path
from datetime import datetime, timezone
import yaml

CONFIG_PATH = "config.yaml"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    if len(sys.argv) < 2:
        print("Usage: python enqueue_comment.py \"<comment text>\" [<source_url>]")
        sys.exit(1)

    comment = sys.argv[1].strip()
    source_url = sys.argv[2] if len(sys.argv) > 2 else "https://example.com/manual"

    cfg = load_config()
    out_dir = Path(cfg["output_dir"]) / "queue"
    out_dir.mkdir(parents=True, exist_ok=True)

    cid = hash_text(comment)
    payload = {
        "id": cid,
        "url": source_url,
        "comment": comment,
        "matched_pattern": "manual",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    out_path = out_dir / f"{cid}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("Enqueued:", out_path)

if __name__ == "__main__":
    main()
