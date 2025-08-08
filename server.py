from flask import Flask, render_template_string, send_file, redirect, url_for
import glob, json, os, shutil, pathlib

app = Flask(__name__)
QUEUE_DIR = "output/queue"
PUBLISHED = "output/published"

INDEX_TMPL = """<!doctype html><html><body>
<h2>Moderation Queue</h2>
<ul>
{% for item in items %}
  <li>
    <b>{{item.id}}</b> - {{item.comment}} <br/>
    <video width=480 controls src="/video/{{item.id}}"></video><br/>
    <form method="post" action="/approve/{{item.id}}">
      <button type="submit">Approve & Publish</button>
    </form>
  </li>
{% endfor %}
</ul>
</body></html>
"""

def load_items():
    items=[]
    for path in glob.glob(f"{QUEUE_DIR}/*.meta.json"):
        with open(path, encoding='utf-8') as f:
            m = json.load(f)
        id = pathlib.Path(path).stem
        with open(f"{QUEUE_DIR}/{id}.json", encoding='utf-8') as f:
            q = json.load(f)
        items.append({"id": id, "meta": m, "comment": q['comment'], "video": m['video']})
    return items

@app.route("/")
def index():
    items = load_items()
    return render_template_string(INDEX_TMPL, items=items)

@app.route("/video/<id>")
def video(id):
    meta = f"{QUEUE_DIR}/{id}.meta.json"
    if not os.path.exists(meta):
        return "not found", 404
    with open(meta, encoding='utf-8') as f:
        m = json.load(f)
    return send_file(m['video'])

@app.route("/approve/<id>", methods=["POST"])
def approve(id):
    src = f"{QUEUE_DIR}/{id}"
    dst = f"{PUBLISHED}/{id}"
    os.makedirs(PUBLISHED, exist_ok=True)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(port=5004, debug=True)
