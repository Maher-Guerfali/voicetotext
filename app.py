import io
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file, jsonify, abort
from openai import OpenAI
from pydub import AudioSegment
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB upload cap

UPLOAD_DIR = Path("uploads")
TRANSCRIPT_DIR = Path("transcripts")
UPLOAD_DIR.mkdir(exist_ok=True)
TRANSCRIPT_DIR.mkdir(exist_ok=True)

# Whisper API has a 25 MB per-request limit. We chunk anything bigger.
WHISPER_LIMIT_BYTES = 24 * 1024 * 1024
CHUNK_MS = 10 * 60 * 1000  # 10-minute chunks

ALLOWED_EXT = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac", "aac"}


def client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        abort(500, "OPENAI_API_KEY is not set. Add it to .env")
    return OpenAI(api_key=key)


def transcribe_file(path: Path, language: str | None) -> str:
    size = path.stat().st_size
    if size <= WHISPER_LIMIT_BYTES:
        with path.open("rb") as f:
            kwargs = {"model": "whisper-1", "file": f}
            if language:
                kwargs["language"] = language
            resp = client().audio.transcriptions.create(**kwargs)
        return resp.text.strip()

    # File too big — split into ~10-minute chunks and transcribe each
    audio = AudioSegment.from_file(path)
    pieces = []
    for i in range(0, len(audio), CHUNK_MS):
        chunk = audio[i:i + CHUNK_MS]
        buf = io.BytesIO()
        buf.name = "chunk.mp3"
        chunk.export(buf, format="mp3", bitrate="64k")
        buf.seek(0)
        kwargs = {"model": "whisper-1", "file": buf}
        if language:
            kwargs["language"] = language
        resp = client().audio.transcriptions.create(**kwargs)
        pieces.append(resp.text.strip())
    return "\n\n".join(pieces)


def write_pdf(text: str, out_path: Path, title: str) -> None:
    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER,
                            leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for para in text.split("\n\n"):
        para = para.replace("\n", "<br/>").strip()
        if para:
            story.append(Paragraph(para, styles["BodyText"]))
            story.append(Spacer(1, 8))
    doc.build(story)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["audio"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"Unsupported format .{ext}"}), 400

    language = (request.form.get("language") or "").strip() or None
    job_id = uuid.uuid4().hex[:12]
    audio_path = UPLOAD_DIR / f"{job_id}.{ext}"
    f.save(audio_path)

    try:
        text = transcribe_file(audio_path, language)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            audio_path.unlink()
        except OSError:
            pass

    txt_path = TRANSCRIPT_DIR / f"{job_id}.txt"
    pdf_path = TRANSCRIPT_DIR / f"{job_id}.pdf"
    txt_path.write_text(text, encoding="utf-8")
    write_pdf(text, pdf_path, title=f.filename)

    return jsonify({
        "id": job_id,
        "text": text,
        "txt_url": f"/download/{job_id}.txt",
        "pdf_url": f"/download/{job_id}.pdf",
    })


@app.route("/download/<name>")
def download(name: str):
    path = TRANSCRIPT_DIR / name
    if not path.exists() or ".." in name:
        abort(404)
    return send_file(path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
