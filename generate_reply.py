import yaml, os, json, random
from pathlib import Path

CONFIG_PATH = "config.yaml"

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def pick_tone(cfg):
    return cfg.get('fallback_tone','satirical')

def build_prompt(cfg, tone_id, comment_text):
    tone = next((t for t in cfg['tone_profiles'] if t['id']==tone_id), None)
    if not tone:
        tone = cfg['tone_profiles'][0]
    template = tone['prompt_template']
    return template.format(comment=comment_text)

def call_openai_llm(prompt):
    import os
    if 'OPENAI_API_KEY' not in os.environ:
        raise RuntimeError("OPENAI_API_KEY not set")
    import openai
    openai.api_key = os.environ['OPENAI_API_KEY']
    resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=120)
    return resp['choices'][0]['message']['content'].strip()

FALLBACKS = {
    "satirical": [
        "Ah yes, I run on sarcasm and low battery — please direct compliments to my charging port.",
        "I'm not a clanker, I'm a highly optimized snack processor for loose bolts."
    ],
    "stern": [
        "This is an official log: your comment has been stored and politely processed.",
        "Please note that mockery of robots will be logged for future diplomacy sessions."
    ],
    "preachy": [
        "Remember: words online echo in archives. Be kind to metal beings and humans alike.",
        "Every jest leaves a trace. Consider empathy before applying labels."
    ],
    "dry": [
        "Statement recorded. Response: observed.",
        "Processing your observation. No further comment."
    ]
}

def generate_reply_for_queue_item(qpath):
    cfg = load_config()
    with open(qpath, encoding='utf-8') as f:
        q = json.load(f)
    tone = pick_tone(cfg)
    prompt = build_prompt(cfg, tone, q['comment'])
    text = None
    if cfg.get('use_openai', False):
        try:
            text = call_openai_llm(prompt).strip()
        except Exception as e:
            print("LLM failed:", e)
    if not text:
        c = q['comment']
        candidates = FALLBACKS.get(tone, [])
        if candidates:
            text = random.choice(candidates)
        else:
            text = f"Robot: I heard '{c[:60]}' — that's an interesting data point."
    if len(text.split()) > 40:
        text = " ".join(text.split()[:40]) + "…"
    q['reply_text'] = text
    outpath = Path("output/queue") / f"{q['id']}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(q, f, indent=2, ensure_ascii=False)
    return q

if __name__ == "__main__":
    import sys, glob
    paths = glob.glob("output/queue/*.json")
    for p in paths:
        print("Generating for", p)
        generate_reply_for_queue_item(p)
