#!/usr/bin/env python3
"""
podcut web UI — upload audio + script, download cleaned podcast.

Run:
    pip install flask
    python app.py
Then open http://localhost:7860
"""

import json
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB upload limit

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

  .options-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
  }

  .options-row label {
    font-size: 0.85rem;
    color: #888;
    white-space: nowrap;
  }

  select {
    background: #111;
    color: #e8e8e8;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.85rem;
    cursor: pointer;
    flex: 1;
  }

  select:focus { outline: 2px solid #555; }

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

  .api-key-row {
    margin-bottom: 24px;
  }

  .api-key-row label {
    font-size: 0.85rem;
    color: #888;
    display: block;
    margin-bottom: 6px;
  }

  .api-key-input {
    background: #111;
    color: #e8e8e8;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.85rem;
    font-family: monospace;
    width: 100%;
  }

  .api-key-input:focus { outline: 2px solid #555; border-color: #555; }

  .api-key-hint {
    font-size: 0.72rem;
    color: #555;
    margin-top: 5px;
  }
</style>
</head>
<body>

<h1>podcut</h1>
<p class="subtitle">Automatically remove bloopers from your podcast recording</p>

<div class="card">

  <div class="api-key-row">
    <label for="apiKeyInput">Anthropic API key</label>
    <input
      class="api-key-input"
      type="password"
      id="apiKeyInput"
      placeholder="sk-ant-..."
      oninput="checkReady()"
      autocomplete="off"
    />
    <div class="api-key-hint">Your key is sent only to this local server and never stored.</div>
  </div>

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

  <div class="options-row">
    <label for="modelSelect">Whisper model</label>
    <select id="modelSelect">
      <option value="tiny">tiny — fastest, least accurate</option>
      <option value="base" selected>base — good balance (default)</option>
      <option value="small">small — better accuracy</option>
      <option value="medium">medium — high accuracy, slower</option>
      <option value="large">large — best accuracy, slowest</option>
    </select>
  </div>

  <button class="btn btn-primary" id="processBtn" disabled onclick="startProcessing()">
    Process podcast
  </button>

  <div class="progress-area" id="progressArea">
    <div class="progress-bar-track">
      <div class="progress-bar-fill" id="progressFill"></div>
    </div>
    <div class="progress-step" id="progressStep">Starting…</div>
  </div>

  <div class="status-error" id="errorBox"></div>

  <button class="btn btn-download" id="downloadBtn" onclick="downloadResult()">
    ⬇ Download cleaned audio
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
  const zone = document.getElementById(type + 'Zone');
  const nameEl = document.getElementById(type + 'Name');
  zone.classList.add('has-file');
  nameEl.textContent = file.name;
  checkReady();
}

function checkReady() {
  const hasAudio = document.getElementById('audioInput').files.length > 0;
  const hasScript = document.getElementById('scriptInput').files.length > 0;
  const hasKey = document.getElementById('apiKeyInput').value.trim().length > 0;
  document.getElementById('processBtn').disabled = !(hasAudio && hasScript && hasKey);
}

async function startProcessing() {
  const audioFile = document.getElementById('audioInput').files[0];
  const scriptFile = document.getElementById('scriptInput').files[0];
  const model = document.getElementById('modelSelect').value;
  const apiKey = document.getElementById('apiKeyInput').value.trim();

  // Reset UI
  document.getElementById('processBtn').disabled = true;
  document.getElementById('downloadBtn').style.display = 'none';
  document.getElementById('errorBox').style.display = 'none';
  document.getElementById('progressArea').style.display = 'block';
  setProgress(0, 'Uploading files…');

  const form = new FormData();
  form.append('audio', audioFile);
  form.append('script', scriptFile);
  form.append('model', model);
  form.append('api_key', apiKey);

  try {
    const res = await fetch('/process', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    currentJobId = data.job_id;
    setProgress(5, 'Queued — starting pipeline…');
    pollInterval = setInterval(pollStatus, 2000);
  } catch (err) {
    showError(err.message);
  }
}

async function pollStatus() {
  if (!currentJobId) return;
  try {
    const res = await fetch('/status/' + currentJobId);
    const data = await res.json();
    setProgress(data.progress, data.step);
    if (data.status === 'done') {
      clearInterval(pollInterval);
      document.getElementById('downloadBtn').style.display = 'block';
      document.getElementById('processBtn').disabled = false;
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
}

function downloadResult() {
  if (currentJobId) window.location.href = '/download/' + currentJobId;
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Background processing pipeline
# ---------------------------------------------------------------------------

def run_pipeline(job_id: str, audio_path: str, script_path: str,
                 output_path: str, model_size: str, api_key: str) -> None:
    try:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        sys.path.insert(0, os.path.dirname(__file__))

        _update(job_id, 10, "Transcribing audio with Whisper… (may take a few minutes)")
        from transcribe import transcribe_audio
        segments = transcribe_audio(audio_path, model_size=model_size)
        if not segments:
            raise ValueError("Whisper produced an empty transcript — is the audio file valid?")

        _update(job_id, 45, "Parsing script…")
        from parse_script import parse_word_doc
        script_text = parse_word_doc(script_path)

        _update(job_id, 60, "Analysing with Claude AI… (may take a moment)")
        from align import detect_bloopers
        analysis = detect_bloopers(segments, script_text)

        if not analysis.segments_to_keep:
            raise ValueError("Claude returned no segments to keep — check your input files.")

        _update(job_id, 85, "Editing audio…")
        from edit_audio import edit_audio
        edit_audio(
            input_path=audio_path,
            segments_to_keep=analysis.segments_to_keep,
            output_path=output_path,
            crossfade_ms=20,
        )

        jobs[job_id].update(status="done", progress=100, step="Done!")

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
    audio = request.files.get("audio")
    script = request.files.get("script")
    if not audio or not script:
        return jsonify(error="Both audio and script files are required."), 400

    model_size = request.form.get("model", "base")
    api_key = request.form.get("api_key", "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify(error="An Anthropic API key is required."), 400

    job_dir = tempfile.mkdtemp(prefix="podcut_")
    audio_path = os.path.join(job_dir, audio.filename)
    script_path = os.path.join(job_dir, script.filename)
    audio.save(audio_path)
    script.save(script_path)

    ext = Path(audio.filename).suffix or ".mp3"
    output_path = os.path.join(job_dir, "cleaned" + ext)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "processing",
        "step": "Starting…",
        "progress": 0,
        "error": None,
        "output": output_path,
        "output_name": "cleaned" + ext,
    }

    t = threading.Thread(
        target=run_pipeline,
        args=(job_id, audio_path, script_path, output_path, model_size, api_key),
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
