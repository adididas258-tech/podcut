#!/usr/bin/env python3
"""
podcut web UI — upload audio + script, download cleaned podcast.

Uses the local fuzzy-matching pipeline from clean_podcast.py.
No API key required.

Run:
    pip install flask
    python app.py
Then open http://localhost:7860
"""

import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB upload limit

if not os.environ.get("GROQ_API_KEY"):
    print(
        "\n⚠  WARNING: GROQ_API_KEY is not set — transcription will fail.\n"
        "   Get a free key at https://console.groq.com\n"
        "   Then restart with:  GROQ_API_KEY=gsk_... python app.py\n"
    )

# In-memory job store  {job_id: {...}}
jobs: dict = {}

# ---------------------------------------------------------------------------
# HTML UI
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>podcut</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f0f0f;
    color: #e8e8e8;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 16px 80px;
  }

  h1 {
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.04em;
    margin-bottom: 6px;
    background: linear-gradient(135deg, #fff 40%, #888);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .subtitle {
    color: #666;
    font-size: 0.95rem;
    margin-bottom: 48px;
    text-align: center;
  }

  .card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    padding: 32px;
    width: 100%;
    max-width: 560px;
  }

  .upload-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
  }

  .drop-zone {
    border: 2px dashed #333;
    border-radius: 12px;
    padding: 28px 16px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    position: relative;
  }

  .drop-zone:hover, .drop-zone.drag-over {
    border-color: #555;
    background: #222;
  }

  .drop-zone.has-file {
    border-color: #3a7a4a;
    background: #1a2a1e;
  }

  .drop-zone input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }

  .drop-icon {
    font-size: 2rem;
    margin-bottom: 8px;
    display: block;
  }

  .drop-label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
    margin-bottom: 4px;
  }

  .drop-hint {
    font-size: 0.75rem;
    color: #555;
  }

  .drop-filename {
    font-size: 0.8rem;
    color: #7ec88a;
    margin-top: 6px;
    word-break: break-all;
  }

  .options-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 24px;
  }

  .option-block label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #666;
    display: block;
    margin-bottom: 6px;
  }

  select, .threshold-input {
    background: #111;
    color: #e8e8e8;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.85rem;
    cursor: pointer;
    width: 100%;
  }

  select:focus, .threshold-input:focus { outline: 2px solid #555; }

  .threshold-input { cursor: text; }

  .threshold-hint {
    font-size: 0.72rem;
    color: #555;
    margin-top: 4px;
  }

  .btn {
    width: 100%;
    padding: 14px;
    font-size: 1rem;
    font-weight: 600;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
  }

  .btn:active { transform: scale(0.98); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

  .btn-primary {
    background: #fff;
    color: #000;
  }

  .btn-download {
    background: #2a6a3a;
    color: #fff;
    margin-top: 16px;
    display: none;
  }

  /* Progress area */
  .progress-area {
    margin-top: 24px;
    display: none;
  }

  .progress-bar-track {
    background: #222;
    border-radius: 99px;
    height: 6px;
    overflow: hidden;
    margin-bottom: 12px;
  }

  .progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #3a8a4a, #5ab86a);
    border-radius: 99px;
    transition: width 0.4s ease;
    width: 0%;
  }

  .progress-step {
    font-size: 0.85rem;
    color: #888;
    min-height: 20px;
  }

  .status-error {
    color: #e07070;
    font-size: 0.85rem;
    margin-top: 12px;
    background: #2a1a1a;
    border-radius: 8px;
    padding: 12px;
    display: none;
  }

  .result-summary {
    margin-top: 16px;
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 0.82rem;
    color: #888;
    display: none;
    line-height: 1.7;
  }

  .result-summary strong { color: #7ec88a; }
</style>
</head>
<body>

<h1>podcut</h1>
<p class="subtitle">Automatically remove bloopers from your podcast recording</p>

<div class="card">

  <div class="upload-grid">
    <!-- Audio upload -->
    <div class="drop-zone" id="audioZone">
      <input type="file" id="audioInput" accept=".mp3,.wav,.m4a,.flac,.ogg,.aac" />
      <span class="drop-icon">🎙️</span>
      <div class="drop-label">Audio file</div>
      <div class="drop-hint">mp3, wav, m4a…</div>
      <div class="drop-filename" id="audioName"></div>
    </div>

    <!-- Script upload -->
    <div class="drop-zone" id="scriptZone">
      <input type="file" id="scriptInput" accept=".docx" />
      <span class="drop-icon">📄</span>
      <div class="drop-label">Script</div>
      <div class="drop-hint">.docx Word document</div>
      <div class="drop-filename" id="scriptName"></div>
    </div>
  </div>

  <div class="options-grid">
    <div class="option-block">
      <label for="modelSelect">Whisper model</label>
      <select id="modelSelect">
        <option value="tiny">tiny — fastest</option>
        <option value="base" selected>base — balanced</option>
        <option value="small">small — better</option>
        <option value="medium">medium — high accuracy</option>
        <option value="large">large — best, slowest</option>
      </select>
    </div>
    <div class="option-block">
      <label for="thresholdInput">Match threshold</label>
      <input
        class="threshold-input"
        type="number"
        id="thresholdInput"
        min="30" max="100" value="70"
      />
      <div class="threshold-hint">0–100. Lower = more lenient.</div>
    </div>
  </div>

  <button class="btn btn-primary" id="processBtn" disabled onclick="startProcessing()">
    Clean podcast
  </button>

  <div class="progress-area" id="progressArea">
    <div class="progress-bar-track">
      <div class="progress-bar-fill" id="progressFill"></div>
    </div>
    <div class="progress-step" id="progressStep">Starting…</div>
  </div>

  <div class="status-error" id="errorBox"></div>

  <div class="result-summary" id="resultSummary"></div>

  <button class="btn btn-download" id="downloadBtn" onclick="downloadResult()">
    Download cleaned audio
  </button>

</div>

<script>
let currentJobId = null;
let pollInterval = null;

// Wire up file inputs
document.getElementById('audioInput').addEventListener('change', e => setFile('audio', e.target.files[0]));
document.getElementById('scriptInput').addEventListener('change', e => setFile('script', e.target.files[0]));

// Drag-over highlight
['audioZone','scriptZone'].forEach(id => {
  const el = document.getElementById(id);
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('drag-over'); });
  el.addEventListener('dragleave', () => el.classList.remove('drag-over'));
  el.addEventListener('drop', e => {
    e.preventDefault();
    el.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const type = id === 'audioZone' ? 'audio' : 'script';
    const input = document.getElementById(type + 'Input');
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    setFile(type, file);
  });
});

function setFile(type, file) {
  if (!file) return;
  document.getElementById(type + 'Zone').classList.add('has-file');
  document.getElementById(type + 'Name').textContent = file.name;
  checkReady();
}

function checkReady() {
  const hasAudio  = document.getElementById('audioInput').files.length > 0;
  const hasScript = document.getElementById('scriptInput').files.length > 0;
  document.getElementById('processBtn').disabled = !(hasAudio && hasScript);
}

async function startProcessing() {
  const audioFile  = document.getElementById('audioInput').files[0];
  const scriptFile = document.getElementById('scriptInput').files[0];
  const model      = document.getElementById('modelSelect').value;
  const threshold  = parseInt(document.getElementById('thresholdInput').value, 10) || 70;

  // Reset UI
  document.getElementById('processBtn').disabled = true;
  document.getElementById('downloadBtn').style.display = 'none';
  document.getElementById('resultSummary').style.display = 'none';
  document.getElementById('errorBox').style.display = 'none';
  document.getElementById('progressArea').style.display = 'block';
  setProgress(0, 'Uploading files…');

  const form = new FormData();
  form.append('audio', audioFile);
  form.append('script', scriptFile);
  form.append('model', model);
  form.append('threshold', threshold);

  try {
    const res = await fetch('/process', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    currentJobId = data.job_id;
    setProgress(5, 'Queued — starting pipeline…');
    pollInterval = setInterval(pollStatus, 2000);
  } catch (err) {
    showError(err.message);
    document.getElementById('processBtn').disabled = false;
  }
}

async function pollStatus() {
  if (!currentJobId) return;
  try {
    const res  = await fetch('/status/' + currentJobId);
    const data = await res.json();
    setProgress(data.progress, data.step);

    if (data.status === 'done') {
      clearInterval(pollInterval);
      document.getElementById('downloadBtn').style.display = 'block';
      document.getElementById('processBtn').disabled = false;
      if (data.summary) {
        const s = data.summary;
        const el = document.getElementById('resultSummary');
        el.innerHTML =
          `<strong>${s.segments_kept}</strong> segment(s) kept &nbsp;·&nbsp; ` +
          `<strong>${s.segments_removed}</strong> blooper(s) removed &nbsp;·&nbsp; ` +
          `<strong>${s.total_kept_s}s</strong> of clean audio &nbsp;·&nbsp; ` +
          `<strong>${s.total_removed_s}s</strong> cut`;
        el.style.display = 'block';
      }
    } else if (data.status === 'error') {
      clearInterval(pollInterval);
      showError(data.error || 'An error occurred.');
      document.getElementById('processBtn').disabled = false;
    }
  } catch (_) { /* network blip, keep polling */ }
}

function setProgress(pct, label) {
  document.getElementById('progressFill').style.width = pct + '%';
  document.getElementById('progressStep').textContent = label;
}

function showError(msg) {
  const box = document.getElementById('errorBox');
  box.textContent = 'Error: ' + msg;
  box.style.display = 'block';
  document.getElementById('progressArea').style.display = 'none';
}

function downloadResult() {
  if (currentJobId) window.location.href = '/download/' + currentJobId;
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Background processing pipeline (uses clean_podcast.py functions directly)
# ---------------------------------------------------------------------------

def _detect_script_language(script_text: str) -> str | None:
    """Return a Whisper language code if we can identify it from the script."""
    import re
    if re.search(r'[\u05d0-\u05ea]', script_text):
        return "he"
    if re.search(r'[\u0600-\u06ff]', script_text):
        return "ar"
    if re.search(r'[\u4e00-\u9fff]', script_text):
        return "zh"
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', script_text):
        return "ja"
    if re.search(r'[\u0400-\u04ff]', script_text):
        return "ru"
    return None


def run_pipeline(job_id: str, audio_path: str, script_path: str,
                 output_path: str, model_size: str, threshold: int) -> None:
    """Run the full clean_podcast pipeline in a background thread."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        # Import the three core functions from our standalone script.
        from clean_podcast import transcribe_audio, parse_script, align_and_detect_bloopers, edit_audio

        _update(job_id, 10, "Transcribing audio with Whisper… (may take a few minutes)")
        # Peek at the script to detect language and skip Whisper's detection step.
        _update(job_id, 12, "Parsing script to detect language…")
        script_text_preview = parse_script(script_path)
        language = _detect_script_language(script_text_preview)
        lang_label = f" (detected: {language})" if language else ""
        _update(job_id, 14, f"Transcribing audio with Whisper{lang_label}…")
        words = transcribe_audio(audio_path, model_size=model_size, language=language)
        if not words:
            raise ValueError("Whisper produced an empty transcript — is the audio file valid?")

        _update(job_id, 45, "Parsing script…")
        script_text = script_text_preview  # already parsed above

        _update(job_id, 55, "Aligning transcript to script (fuzzy matching)…")
        def _align_progress(pct, step):
            _update(job_id, pct, step)
        segments = align_and_detect_bloopers(words, script_text, match_threshold=threshold,
                                             progress_callback=_align_progress)

        _update(job_id, 85, "Editing audio…")
        edit_audio(audio_path, segments, output_path, crossfade_ms=20)

        # Build a summary for the UI.
        kept    = [s for s in segments if s.label == "keep"]
        blooper = [s for s in segments if s.label == "blooper"]
        summary = {
            "segments_kept":    len(kept),
            "segments_removed": len(blooper),
            "total_kept_s":     round(sum(s.end - s.start for s in kept),    1),
            "total_removed_s":  round(sum(s.end - s.start for s in blooper), 1),
        }
        jobs[job_id].update(status="done", progress=100, step="Done!", summary=summary)

    except Exception as exc:
        jobs[job_id].update(status="error", error=str(exc))


def _update(job_id: str, progress: int, step: str) -> None:
    jobs[job_id]["progress"] = progress
    jobs[job_id]["step"] = step


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/process", methods=["POST"])
def process():
    try:
        return _process_inner()
    except Exception as exc:
        return jsonify(error=str(exc)), 500


def _process_inner():
    audio  = request.files.get("audio")
    script = request.files.get("script")
    if not audio or not script:
        return jsonify(error="Both audio and script files are required."), 400

    model_size = request.form.get("model", "base")
    try:
        threshold = int(request.form.get("threshold") or 70)
    except (ValueError, TypeError):
        threshold = 70

    # Save uploads to a temp directory with safe ASCII filenames.
    job_dir     = tempfile.mkdtemp(prefix="podcut_")
    ext         = Path(audio.filename).suffix or ".mp3"
    audio_path  = os.path.join(job_dir, "audio" + ext)
    script_path = os.path.join(job_dir, "script.docx")
    audio.save(audio_path)
    script.save(script_path)

    output_path = os.path.join(job_dir, "cleaned" + ext)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status":      "processing",
        "step":        "Starting…",
        "progress":    0,
        "error":       None,
        "summary":     None,
        "output":      output_path,
        "output_name": "cleaned" + ext,
    }

    t = threading.Thread(
        target=run_pipeline,
        args=(job_id, audio_path, script_path, output_path, model_size, threshold),
        daemon=True,
    )
    t.start()

    return jsonify(job_id=job_id)


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job not found"), 404
    return jsonify(
        status=job["status"],
        step=job["step"],
        progress=job["progress"],
        error=job.get("error"),
        summary=job.get("summary"),
    )


@app.route("/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job not found"), 404
    if job["status"] != "done":
        return jsonify(error="Not ready yet"), 400
    return send_file(
        job["output"],
        as_attachment=True,
        download_name=job["output_name"],
    )


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("podcut UI running at http://localhost:7860")
    app.run(host="0.0.0.0", port=7860, debug=False)
