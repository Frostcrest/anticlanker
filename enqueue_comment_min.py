# enqueue_comment_min.py
import json, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone

def hash_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def main():
    if len(sys.argv) < 2:
        print("Usage: python enqueue_comment_min.py \"<comment text>\" [<source_url>] [<output_dir>]")
        sys.exit(1)

    comment = sys.argv[1].strip()
    source_url = sys.argv[2] if len(sys.argv) > 2 else "manual://test"
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("./output/queue")

    output_dir.mkdir(parents=True, exist_ok=True)

    cid = hash_text(comment)
    payload = {
        "id": cid,
        "url": source_url,
        "comment": comment,
        "matched_pattern": "manual",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    out_path = output_dir / f"{cid}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Enqueued:", out_path)

if __name__ == "__main__":
    main()
