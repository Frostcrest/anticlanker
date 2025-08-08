# enqueue_comment_min.py
import json, sys
from pathlib import Path
from datetime import datetime, timezone
from common import sha256, queue_dir

def main():
    if len(sys.argv) < 2:
        print("Usage: python enqueue_comment_min.py \"<comment text>\" [<source_url>] [<output_dir>]")
        sys.exit(1)

    comment = sys.argv[1].strip()
    source_url = sys.argv[2] if len(sys.argv) > 2 else "manual://test"
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else queue_dir()

    output_dir.mkdir(parents=True, exist_ok=True)

    cid = sha256(comment)
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
