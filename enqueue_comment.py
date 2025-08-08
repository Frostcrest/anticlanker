# enqueue_comment.py
import json, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone

CONFIG_PATH = "config.yaml"

def sha(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load_output_dir():
    """Try config.yaml; if anything fails, use ./output/queue"""
    try:
        import yaml
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        out = Path(cfg.get("output_dir", "./output")) / "queue"
    except Exception:
        out = Path("./output") / "queue"
    out.mkdir(parents=True, exist_ok=True)
    return out

def main():
    if len(sys.argv) < 2:
        print("Usage: python enqueue_comment.py \"<comment text>\" [<source_url>] [--out <output_dir>]")
        sys.exit(1)

    # parse args
    args = sys.argv[1:]
    comment = args[0].strip()
    source_url = "manual://test"
    out_dir_override = None

    if len(args) >= 2 and not args[1].startswith("--"):
        source_url = args[1].strip()

    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_dir_override = Path(args[idx+1])

    out_dir = out_dir_override or load_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    cid = sha(comment)
    payload = {
        "id": cid,
        "url": source_url,
        "comment": comment,
        "matched_pattern": "manual",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    out_path = out_dir / f"{cid}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Enqueued:", out_path)

if __name__ == "__main__":
    main()
