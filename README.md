# Voice → Text

Tiny Flask app: upload an audio file, get a full transcript, download as `.txt` or `.pdf`.

Uses **OpenAI Whisper** (`whisper-1`) — most accurate for transcription, handles many languages, ~$0.006/min.

## Quick start

```bash
# 1. install ffmpeg (required by pydub for chunking large files)
#    macOS:   brew install ffmpeg
#    Ubuntu:  sudo apt install ffmpeg

# 2. install python deps
pip install -r requirements.txt

# 3. set your key
cp .env.example .env
# edit .env and paste your OPENAI_API_KEY

# 4. run
python app.py
# open http://localhost:5000
```

## Notes

- Files up to **25 MB** go straight to Whisper.
- Larger files are auto-split into 10-minute chunks (re-encoded to 64 kbps mp3) and stitched back together.
- Supported formats: mp3, mp4, m4a, wav, webm, ogg, flac, aac, mpga, mpeg.
- The optional **Language** field (ISO-639-1 like `en`, `fr`, `ar`) speeds things up and improves accuracy if you know the audio language.

## Why Whisper over Gemini / Claude?

- **Whisper**: purpose-built for ASR, best accuracy, cheap, language-agnostic.
- **Gemini 2.0**: works for audio but tuned more for understanding than verbatim transcription.
- **Claude**: doesn't accept raw audio input — would need transcription first anyway.
