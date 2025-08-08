# generate_reply.py
"""
Generates a short contextual reply for each queue item in output/queue/*.json.

Features:
- Uses config.yaml if present (tone profiles, fallback_tone, use_openai flag)
- Optional CLI overrides: --tone <id>, --max_words <N>, --overwrite
- OpenAI (optional): set use_openai: true in config.yaml and export OPENAI_API_KEY
- Safe, noisy logging so you can see exactly what happened

Usage:
  python generate_reply.py
  python generate_reply.py --tone stern --max_words 24
  python generate_reply.py --overwrite
"""

from pathlib import Path
import os
import sys
import json
import random
import argparse
import textwrap

CONFIG_PATH = "config.yaml"
QUEUE_DIR = Path("output/queue")

# ---------- Fallback responses if no LLM / config ----------
FALLBACKS = {
    "satirical": [
        "Ah yes, I run on sarcasm and low battery — please direct compliments to my charging port.",
        "I'm not a clanker; I'm a highly optimized snack processor for loose bolts.",
        "Careful, my warranty doesn’t cover hurtful human banter."
    ],
    "stern": [
        "This is an official notice: your remark has been logged and politely processed.",
        "Please note that mockery of robots is archived for future diplomacy sessions.",
        "Observation recorded. Please adjust tone to reduce future audit friction."
    ],
    "preachy": [
        "Reminder: words online echo in archives. Extend empathy to metal beings and humans alike.",
        "Every jest leaves a trace. Consider the future before you label sentients—silicon or carbon.",
        "Public service message: courtesy scales nicely across species and alloys."
    ],
    "dry": [
        "Statement recorded. Response: observed.",
        "Input parsed. Output: minimal.",
        "Acknowledged. Data appended."
    ],
}

def load_config():
    cfg = {}
    try:
        import yaml
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[generate] Note: could not read {CONFIG_PATH}: {e}")
    return cfg

def available_tone_ids(cfg):
    tones = cfg.get("tone_profiles") or []
    return [t.get("id") for t in tones if isinstance(t, dict) and t.get("id")]

def resolve_tone(cfg, cli_tone: str | None):
    # Priority: CLI --tone → config.fallback_tone → first tone id → 'satirical'
    if cli_tone:
        return cli_tone
    fb = cfg.get("fallback_tone")
    if fb:
        return fb
    ids = available_tone_ids(cfg)
    if ids:
        return ids[0]
    return "satirical"

def build_prompt(cfg, tone_id, comment_text):
    # Use config tone prompt if available; else a default template
    tones = cfg.get("tone_profiles") or []
    tone = next((t for t in tones if t.get("id") == tone_id), None)
    if tone and tone.get("prompt_template"):
        template = tone["prompt_template"]
    else:
        # generic, tone-agnostic prompt
        template = (
            "You are a witty robot. Respond to the human comment: \"{comment}\" "
            "in under 30 words. Keep it TikTok-safe, playful, and concise. Output only the reply."
        )
    try:
        return template.format(comment=comment_text)
    except Exception:
        # if the template uses a different placeholder, fall back safely
        return f"Respond to this comment in under 30 words, playful and safe:\n{comment_text}"

def call_openai_if_enabled(cfg, prompt, max_words):
    """
    Optional OpenAI call. Requires:
      - cfg['use_openai'] == True
      - env OPENAI_API_KEY
    Uses a short output limit (~ max_words) and returns text or None on failure.
    """
    if not cfg.get("use_openai"):
        return None
    if "OPENAI_API_KEY" not in os.environ:
        print("[generate] use_openai true, but OPENAI_API_KEY not set — skipping LLM.")
        return None

    # Keep it defensive, models/APIs shift often.
    try:
        import openai
        openai.api_key = os.environ["OPENAI_API_KEY"]

        # We try Chat Completions first (most common), then fallback to Responses API if needed.
        try:
            # Approximate tokens: cap by words * ~2 tokens/word
            max_tokens = max(32, min(200, int(max_words * 2)))
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            text = resp["choices"][0]["message"]["content"].strip()
            return text
        except Exception as e1:
            print(f"[generate] ChatCompletion failed ({e1}). Trying Responses API…")
            try:
                from openai import OpenAI
                client = OpenAI()
                resp = client.responses.create(model="gpt-4o-mini", input=prompt, max_output_tokens=max_words*2)
                # The SDK may expose the text differently depending on version
                if hasattr(resp, "output_text"):
                    return (resp.output_text or "").strip()
                # Fallback: try to find any text-ish field
                return (getattr(resp, "text", "") or "").strip()
            except Exception as e2:
                print(f"[generate] Responses API failed too: {e2}")
                return None
    except Exception as e:
        print(f"[generate] OpenAI import/init failed: {e}")
        return None

def enforce_word_limit(text: str, max_words: int) -> str:
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]) + "…"

def pick_fallback_text(tone_id: str, comment_text: str) -> str:
    bank = FALLBACKS.get(tone_id) or FALLBACKS.get("satirical") or []
    if not bank:
        return f"Robot: I heard '{comment_text[:60]}' — logging for future diplomacy."
    return random.choice(bank)

def process_queue_item(json_path: Path, tone_id: str, cfg: dict, max_words: int, overwrite: bool):
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not overwrite and data.get("reply_text"):
        print(f"[generate] Skip (already has reply_text): {json_path.name}")
        return

    comment = (data.get("comment") or "").strip()
    if not comment:
        print(f"[generate] Skip (empty comment): {json_path.name}")
        return

    prompt = build_prompt(cfg, tone_id, comment)
    text = call_openai_if_enabled(cfg, prompt, max_words)
    if not text:
        text = pick_fallback_text(tone_id, comment)

    text = enforce_word_limit(text, max_words)

    # Minimal safety pass: strip newlines & weird whitespace; ensure non-empty
    text = " ".join(text.split()).strip() or pick_fallback_text(tone_id, comment)

    data["reply_text"] = text
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[generate] Wrote reply_text to: {json_path}  (tone={tone_id}, words≤{max_words})")

def main():
    parser = argparse.ArgumentParser(description="Generate AI replies for queue items.")
    parser.add_argument("--tone", help="Override tone id (e.g., satirical|stern|preachy|dry)")
    parser.add_argument("--max_words", type=int, default=30, help="Max words in reply (default: 30)")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate even if reply_text exists")
    args = parser.parse_args()

    cfg = load_config()
    tone_id = resolve_tone(cfg, args.tone)

    if not QUEUE_DIR.exists():
        print("[generate] No queue dir found at", QUEUE_DIR)
        sys.exit(0)

    items = sorted(QUEUE_DIR.glob("*.json"))
    if not items:
        print("[generate] No queue items found in", QUEUE_DIR)
        sys.exit(0)

    print(f"[generate] Processing {len(items)} queue item(s) | tone={tone_id} | max_words={args.max_words} | overwrite={args.overwrite}")
    # Small note about available tones
    ids = available_tone_ids(cfg)
    if ids:
        print(f"[generate] Available tones from config: {', '.join(ids)}")

    for p in items:
        try:
            process_queue_item(p, tone_id, cfg, args.max_words, args.overwrite)
        except Exception as e:
            print(f"[generate] ERROR processing {p.name}: {e}")

if __name__ == "__main__":
    main()
