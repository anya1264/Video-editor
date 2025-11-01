import os
import uuid
import shutil
import subprocess
from pathlib import Path
from flask import Flask, request, send_file, redirect, url_for, render_template_string, flash

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
ALLOWED_IMG = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg"}

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "cambiami_per_favore")

INDEX_HTML = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>MP3 + Immagine → MP4</title>
  <style>
    body { font-family: Arial, Helvetica, sans-serif; margin: 40px; }
    form { display: flex; flex-direction: column; gap: 10px; max-width: 420px; }
    input[type=file] { padding: 6px; }
    .note { font-size: 0.9rem; color: #555; margin-top: 6px; }
    .flash { color: darkred; }
  </style>
</head>
<body>
  <h1>Converti MP3 + Immagine → MP4</h1>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="flash">{{ messages[0] }}</div>
    {% endif %}
  {% endwith %}
  <form method="post" action="/convert" enctype="multipart/form-data">
    <label>Immagine (png/jpg/webp): <input type="file" name="image" accept="image/*" required></label>
    <label>Audio (mp3/wav/m4a/ogg): <input type="file" name="audio" accept="audio/*" required></label>
    <label>Durata massima opzionale (secondi): <input type="number" name="max_seconds" min="1" placeholder="lascia vuoto per usare durata audio"></label>
    <button type="submit">Genera MP4</button>
  </form>
  <p class="note">Il file risultante verrà scaricato automaticamente.</p>
</body>
</html>
"""

def secure_ext(filename):
    return Path(filename).suffix.lower()

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/convert", methods=["POST"])
def convert():
    if "image" not in request.files or "audio" not in request.files:
        flash("Devi caricare sia l'immagine che l'audio.")
        return redirect(url_for("index"))

    img = request.files["image"]
    aud = request.files["audio"]
    max_seconds = request.form.get("max_seconds", type=int)

    if img.filename == "" or aud.filename == "":
        flash("File non valido.")
        return redirect(url_for("index"))

    img_ext = secure_ext(img.filename)
    aud_ext = secure_ext(aud.filename)

    if img_ext not in ALLOWED_IMG:
        flash(f"Tipo immagine non permesso: {img_ext}")
        return redirect(url_for("index"))
    if aud_ext not in ALLOWED_AUDIO:
        flash(f"Tipo audio non permesso: {aud_ext}")
        return redirect(url_for("index"))

    job_id = uuid.uuid4().hex
    work_dir = UPLOAD_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    img_path = work_dir / f"image{img_ext}"
    aud_path = work_dir / f"audio{aud_ext}"
    out_path = OUTPUT_DIR / f"{job_id}.mp4"

    try:
        img.save(img_path)
        aud.save(aud_path)
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-framerate", "2",
            "-i", str(img_path), "-i", str(aud_path)
        ]
        if max_seconds and max_seconds > 0:
            cmd += ["-t", str(int(max_seconds))]
        cmd += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-pix_fmt", "yuv420p",
            str(out_path)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            flash("Errore nella conversione ffmpeg.")
            return redirect(url_for("index"))
        return send_file(str(out_path), as_attachment=True, download_name=f"{job_id}.mp4")
    except subprocess.TimeoutExpired:
        flash("ffmpeg ha impiegato troppo tempo.")
        return redirect(url_for("index"))
    except Exception:
        flash("Errore imprevisto sul server.")
        return redirect(url_for("index"))
    finally:
        try:
            if work_dir.exists():
                shutil.rmtree(work_dir)
        except Exception:
            pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), debug=True)
