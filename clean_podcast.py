#!/usr/bin/env python3
"""
clean_podcast.py — Podcast blooper cleaner (fuzzy-matching edition)

Transcribes a podcast host's raw audio recording with OpenAI Whisper,
aligns it word-by-word to a Word-document script using fuzzy string
matching, removes bloopers / restarts / off-script passages, and exports
a clean stitched audio file.

No cloud API required — everything runs locally.

Usage:
    python clean_podcast.py --audio recording.mp3 --script script.docx --output cleaned.mp3

    # Tune the Whisper model size for accuracy vs. speed:
    python clean_podcast.py --audio raw.wav --script ep1.docx --output ep1_clean.wav --model medium

    # Save a JSON log of every kept / removed segment:
    python clean_podcast.py --audio raw.mp3 --script ep1.docx --output out.mp3 --save-log

    # Disable the inter-segment crossfade:
    python clean_podcast.py --audio raw.mp3 --script ep1.docx --output out.mp3 --no-crossfade

Requirements:
    pip install groq python-docx pydub rapidfuzz
    ffmpeg must be installed (apt install ffmpeg  /  brew install ffmpeg)
    GROQ_API_KEY must be set (free key at https://console.groq.com)
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Word:
    """A single transcribed word with its audio timestamps."""
    text: str    # Raw text as returned by Whisper
    norm: str    # Lowercase, punctuation-stripped form used for matching
    start: float # Start time in seconds
    end: float   # End time in seconds


@dataclass
class Segment:
    """A contiguous time range in the audio, labelled keep or blooper."""
    start: float  # Segment start time in seconds
    end: float    # Segment end time in seconds
    label: str    # "keep" or "blooper"
    note: str     # Human-readable description (script excerpt or reason)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Transcribe audio with Whisper (word-level timestamps)
# ─────────────────────────────────────────────────────────────────────────────

def _compress_for_groq(audio_path: str) -> tuple[str, bool]:
    """
    Return a path to an audio file that is guaranteed to be under 25 MB
    (Groq's upload limit).  If the original is already small enough, return
    it unchanged.  Otherwise re-encode to 16 kHz mono MP3 @ 32 kbps via
    ffmpeg, which keeps a 60-minute file well under 15 MB.

    Returns (path, is_temp).  The caller must delete the temp file when done.
    """
    import subprocess
    import tempfile

    limit = 24 * 1024 * 1024  # 24 MB — leave 1 MB headroom
    if os.path.getsize(audio_path) <= limit:
        return audio_path, False

    print("  Audio > 24 MB — compressing to 16 kHz mono Opus for upload…")
    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-i", audio_path,
         "-ar", "16000", "-ac", "1", "-c:a", "libopus", "-b:a", "16k", tmp.name],
        check=True, capture_output=True,
    )
    return tmp.name, True


def transcribe_audio(audio_path: str, model_size: str = "base",
                     language: str | None = None,
                     _already_compressed: bool = False) -> list[Word]:
    """
    Transcribe audio via the Groq Whisper API (whisper-large-v3-turbo).

    Groq runs at ~189× real-time, so a 30-minute podcast finishes in
    roughly 10 seconds.  Requires the GROQ_API_KEY environment variable.

    Large files (> 24 MB) are automatically compressed to a small MP3
    before upload so they stay within Groq's 25 MB limit.

    Results are cached to ``<audio>.whisper_cache.json`` so repeat runs
    skip the API call entirely.

    Args:
        audio_path:  Path to the raw audio file (.mp3, .wav, .m4a, …).
        model_size:  Ignored (kept for API compatibility — Groq always uses
                     whisper-large-v3-turbo which is both fastest and best).
        language:    BCP-47 language code (e.g. "he", "en").  When provided,
                     Groq skips language detection.

    Returns:
        List of Word objects ordered by time.
    """
    # ── Cache check ──────────────────────────────────────────────────────── #
    cache_path = audio_path + ".whisper_cache.json"
    try:
        audio_mtime = os.path.getmtime(audio_path)
    except OSError:
        audio_mtime = None

    if os.path.isfile(cache_path) and audio_mtime is not None:
        try:
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            if abs(cached.get("audio_mtime", 0) - audio_mtime) < 1:
                words = [Word(**w) for w in cached["words"]]
                print(f"  Transcript loaded from cache ({len(words)} words).")
                return words
        except Exception:
            pass  # corrupt cache — fall through to re-transcribe

    # ── Groq API ─────────────────────────────────────────────────────────── #
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        sys.exit(
            "Error: GROQ_API_KEY is not set.\n"
            "Get a free key at https://console.groq.com\n"
            "Then: export GROQ_API_KEY=gsk_..."
        )

    try:
        from groq import Groq
    except ImportError:
        sys.exit(
            "Error: groq package is not installed.\n"
            "Fix: pip install groq"
        )

    if _already_compressed:
        upload_path, is_temp = audio_path, False
    else:
        upload_path, is_temp = _compress_for_groq(audio_path)
    try:
        lang_label = f" (language: {language})" if language else ""
        print(f"  Sending to Groq whisper-large-v3-turbo{lang_label}…")
        client = Groq(api_key=groq_key)
        with open(upload_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(upload_path), f),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language=language,
            )
    finally:
        if is_temp:
            try:
                os.unlink(upload_path)
            except Exception:
                pass

    # ── Parse segments → Words ────────────────────────────────────────────── #
    words: list[Word] = []
    for seg in transcription.segments:
        raw_words = seg.text.strip().split()
        if not raw_words:
            continue
        step = (seg.end - seg.start) / len(raw_words)
        for i, raw in enumerate(raw_words):
            words.append(Word(
                text=raw,
                norm=_normalize(raw),
                start=seg.start + i * step,
                end=seg.start + (i + 1) * step,
            ))

    print(f"  Transcription complete: {len(words)} words.")

    # ── Save cache ────────────────────────────────────────────────────────── #
    if audio_mtime is not None:
        try:
            cache_data = {
                "audio_mtime": audio_mtime,
                "words": [
                    {"text": w.text, "norm": w.norm,
                     "start": w.start, "end": w.end}
                    for w in words
                ],
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False)
            print(f"  Transcript cached → '{cache_path}'")
        except Exception:
            pass

    return words


def _normalize(word: str) -> str:
    """
    Strip punctuation and lowercase a word for fuzzy comparison.
    Keeps letters, digits, and apostrophes (contractions like "don't").
    """
    return re.sub(r"[^\w']", "", word.lower()).replace("_", "")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Parse the Word-document script
# ─────────────────────────────────────────────────────────────────────────────

def parse_script(docx_path: str) -> str:
    """
    Extract plain narration text from a .docx file.

    Only plain (non-highlighted, non-bold) runs are included.  Highlighted
    and bold text are treated as stage directions / speaker notes and skipped
    so they don't pollute the narration text the audio is compared against.

    Args:
        docx_path: Path to the Word document.

    Returns:
        Script text as a single string; paragraphs separated by newlines.
    """
    try:
        import docx
        from docx.enum.text import WD_COLOR_INDEX
    except ImportError:
        sys.exit(
            "Error: python-docx is not installed.\n"
            "Fix: pip install python-docx"
        )

    doc = docx.Document(docx_path)
    paragraphs: list[str] = []

    for para in doc.paragraphs:
        # Collect only non-highlighted runs (highlighted = stage direction).
        parts = []
        for run in para.runs:
            color = run.font.highlight_color
            is_highlighted = (color is not None and color != WD_COLOR_INDEX.AUTO)
            is_bold = bool(run.bold)
            if not is_highlighted and not is_bold:
                parts.append(run.text)

        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        sys.exit(
            f"Error: No narration text found in '{docx_path}'.\n"
            "Is the file empty, or is all text highlighted?"
        )

    script = "\n".join(paragraphs)
    word_count = len(script.split())
    print(f"  Script parsed: {len(paragraphs)} paragraph(s), {word_count} words.")
    return script


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Fuzzy alignment: match script sentences to transcript positions
# ─────────────────────────────────────────────────────────────────────────────

def align_and_detect_bloopers(
    transcript_words: list[Word],
    script_text: str,
    match_threshold: int = 70,
    progress_callback=None,
) -> list[Segment]:
    """
    Align the transcript to the script and label every time range as either
    'keep' (matches script) or 'blooper' (doesn't match / is a restart).

    Algorithm overview
    ------------------
    1. Split the script into sentences (alignment units).
    2. For each sentence, slide a fixed-width word-window over the transcript
       and score it with rapidfuzz.fuzz.ratio.  Every window scoring above
       `match_threshold` is recorded as a candidate match.
    3. A greedy left-to-right pass picks the *last* high-scoring candidate
       for each sentence (among those that start after the previous sentence
       ended).  Preferring the latest occurrence is what implements
       "keep the last clean take" for restarts.
    4. The time spans between (and around) the chosen matches are labelled
       as bloopers.

    Args:
        transcript_words:  Word objects from Whisper, ordered by time.
        script_text:       Full narration text from the Word document.
        match_threshold:   Minimum rapidfuzz ratio (0-100) to count as a
                           match.  Lower = more lenient (useful for accented
                           speakers or noisier audio).

    Returns:
        Ordered list of Segment objects spanning the full recording duration.
    """
    try:
        from rapidfuzz import fuzz as _fuzz  # noqa: F401 — just to check install
    except ImportError:
        sys.exit(
            "Error: rapidfuzz is not installed.\n"
            "Fix: pip install rapidfuzz"
        )

    # Pre-compute normalized transcript word list for fast windowed access.
    norm_transcript = [w.norm for w in transcript_words]

    # Split the script into sentence-level alignment units.
    script_sentences = _split_sentences(script_text)
    print(f"  Script split into {len(script_sentences)} alignment sentence(s).")

    # Single-pass alignment: for each sentence scan forward from where the
    # previous match ended, so we never re-scan positions we've already passed.
    # This turns the O(sentences × transcript) scan into roughly O(transcript).
    print("  Aligning transcript to script (sentence by sentence)…")
    T = len(norm_transcript)
    S = len(script_sentences)
    chosen_matches: list[tuple[int, int] | None] = []
    min_start = 0

    for idx, sentence in enumerate(script_sentences):
        if progress_callback and S > 0:
            pct = 55 + int(30 * idx / S)  # 55 % → 85 % during alignment
            progress_callback(pct, f"Aligning sentence {idx + 1}/{S}…")

        sent_words = [_normalize(w) for w in sentence.split() if _normalize(w)]
        if len(sent_words) < 2:
            chosen_matches.append(None)
            continue

        # Search a bounded window ahead to stay fast; fall back to full remainder.
        lookahead = max(len(sent_words) * 15, (T - min_start) // max(S - idx, 1) * 4 + 200)
        end_at = min(T, min_start + lookahead)
        candidates = _find_all_windows(sent_words, norm_transcript, match_threshold,
                                        start_from=min_start, end_at=end_at)
        if not candidates:
            # Wider fallback: scan the full remaining transcript.
            candidates = _find_all_windows(sent_words, norm_transcript, match_threshold,
                                            start_from=min_start, end_at=T)

        if not candidates:
            chosen_matches.append(None)
            continue

        max_score = max(sc for _, _, sc in candidates)
        top = [(s, e, sc) for s, e, sc in candidates if sc >= max_score * 0.85]
        best = max(top, key=lambda x: x[0])  # latest start = last clean take
        chosen_matches.append((best[0], best[1]))
        min_start = best[1]  # advance cursor past this match

    # --- Phase C: convert word-index ranges to time-based Segments --------- #
    segments = _build_segments(transcript_words, chosen_matches, script_sentences)

    n_keep = sum(1 for s in segments if s.label == "keep")
    n_drop = sum(1 for s in segments if s.label == "blooper")
    print(f"  Alignment done: {n_keep} kept segment(s), {n_drop} blooper segment(s).")
    return segments


# ── helpers for align_and_detect_bloopers ────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """
    Split script text into sentences / logical chunks.

    Splits on:
      • Sentence-ending punctuation (. ! ?) followed by whitespace
      • Paragraph breaks (newlines)

    Very short fragments (< 3 words) are merged with the next sentence so
    that short phrases like "OK." don't create unreliable anchors.
    """
    raw = re.split(r'(?<=[.!?])\s+|\n+', text)
    sentences: list[str] = []
    carry = ""

    for chunk in raw:
        chunk = chunk.strip()
        if not chunk:
            continue
        combined = (carry + " " + chunk).strip() if carry else chunk
        # Accumulate until the chunk is long enough to be a useful anchor.
        if len(combined.split()) < 3:
            carry = combined
        else:
            sentences.append(combined)
            carry = ""

    if carry:  # flush any leftover short text
        if sentences:
            sentences[-1] += " " + carry
        else:
            sentences.append(carry)

    return sentences


def _find_all_windows(
    sent_words: list[str],
    norm_transcript: list[str],
    threshold: int,
    start_from: int = 0,
    end_at: int | None = None,
) -> list[tuple[int, int, float]]:
    """
    Slide a window of len(sent_words) words across the transcript and return
    every position that scores >= threshold.

    A small slack (±n/5 extra words) is tried at each position so that filler
    words like "um" or "uh" inserted between script words don't cause a miss.

    start_from / end_at limit the search range so callers can avoid
    re-scanning positions that have already been matched.

    Returns a list of (start_idx, end_idx, score) tuples, sorted by start_idx.
    """
    from rapidfuzz import fuzz

    n = len(sent_words)
    if end_at is None:
        end_at = len(norm_transcript)
    sent_str = " ".join(sent_words)
    # Maximum extra words to tolerate (fillers, hesitations).
    slack = max(2, n // 5)
    matches: list[tuple[int, int, float]] = []

    for i in range(start_from, min(end_at, len(norm_transcript) - n + 1)):
        best_score = 0.0
        best_end = i + n

        # Try the exact window size and slightly larger windows.
        for extra in range(0, slack + 1):
            end = i + n + extra
            if end > len(norm_transcript):
                break
            window_str = " ".join(norm_transcript[i:end])
            score = fuzz.ratio(sent_str, window_str, score_cutoff=best_score)
            if score > best_score:
                best_score = score
                best_end = end
                if best_score == 100:
                    break  # perfect match — no need to try wider windows

        if best_score >= threshold:
            matches.append((i, best_end, best_score))
            if best_score == 100:
                break  # exact match found — stop scanning

    return matches


def _pick_best_path(
    all_candidates: list[list[tuple[int, int, float]]],
) -> list[tuple[int, int] | None]:
    """
    Greedy left-to-right pass: for each script sentence pick the *last*
    high-scoring candidate match that starts after the previous sentence ended.

    "Last clean take" heuristic:
      Among all valid candidates (score >= 85 % of the sentence's best score),
      pick the one with the highest start index (latest in the recording).
      When the host restarts, the final correct read comes latest — so this
      naturally keeps the intended performance and discards retakes.

    Returns a list of (start_word_idx, end_word_idx) or None per sentence.
    """
    chosen: list[tuple[int, int] | None] = []
    min_start = 0  # transcript cursor: next match must begin at or after this

    for candidates in all_candidates:
        if not candidates:
            chosen.append(None)
            continue

        # Filter to candidates that respect the monotone ordering constraint.
        valid = [(s, e, sc) for s, e, sc in candidates if s >= min_start]

        if not valid:
            # No valid position found — sentence may be missing from recording.
            chosen.append(None)
            continue

        # Among valid candidates, consider only those near the best score,
        # then take the latest one (= last clean take).
        max_score = max(sc for _, _, sc in valid)
        top = [(s, e, sc) for s, e, sc in valid if sc >= max_score * 0.85]
        best = max(top, key=lambda x: x[0])  # latest start = last clean take

        chosen.append((best[0], best[1]))
        min_start = best[1]  # advance cursor past this match

    return chosen


def _build_segments(
    transcript_words: list[Word],
    chosen_matches: list[tuple[int, int] | None],
    script_sentences: list[str],
) -> list[Segment]:
    """
    Convert word-index ranges to time-based Segment objects.

    Gaps between kept windows are labelled as bloopers (restarts, false
    starts, off-script tangents, long silences, etc.).
    """
    segments: list[Segment] = []
    total = len(transcript_words)

    # Flatten to a list of (start_idx, end_idx, sentence_label).
    kept_ranges = [
        (s, e, sent)
        for (s, e), sent in (
            (m, sc) for m, sc in zip(chosen_matches, script_sentences)
            if m is not None
        )
    ]

    if not kept_ranges:
        # Nothing matched at all — label the entire recording as a blooper.
        if transcript_words:
            segments.append(Segment(
                start=transcript_words[0].start,
                end=transcript_words[-1].end,
                label="blooper",
                note="No script sentences matched the transcript",
            ))
        return segments

    prev_end_idx = 0  # transcript word index tracking how far we've consumed

    for start_idx, end_idx, sentence in kept_ranges:
        # ── Gap before this match ── #
        if start_idx > prev_end_idx:
            gap_start = transcript_words[prev_end_idx].start
            gap_end   = transcript_words[start_idx - 1].end
            # Only emit the gap if it's meaningfully long (> 100 ms).
            if gap_end - gap_start > 0.1:
                segments.append(Segment(
                    start=gap_start,
                    end=gap_end,
                    label="blooper",
                    note="Restart / off-script / silence",
                ))

        # ── Kept match ── #
        real_end = min(end_idx, total)
        keep_start = transcript_words[start_idx].start
        keep_end   = transcript_words[real_end - 1].end
        # Trim the script excerpt shown in the log to a readable length.
        excerpt = sentence[:72] + ("…" if len(sentence) > 72 else "")
        segments.append(Segment(
            start=keep_start,
            end=keep_end,
            label="keep",
            note=excerpt,
        ))
        prev_end_idx = real_end

    # ── Tail after last kept match ── #
    if prev_end_idx < total:
        tail_start = transcript_words[prev_end_idx].start
        tail_end   = transcript_words[-1].end
        if tail_end - tail_start > 0.1:
            segments.append(Segment(
                start=tail_start,
                end=tail_end,
                label="blooper",
                note="Trailing audio after last script sentence",
            ))

    return segments


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Audio editing: stitch together the kept segments
# ─────────────────────────────────────────────────────────────────────────────

def edit_audio(
    input_path: str,
    segments: list[Segment],
    output_path: str,
    crossfade_ms: int = 20,   # kept for API compatibility; not used in copy mode
) -> None:
    """
    Extract all 'keep' segments from the source audio and concatenate them
    into a single clean output file using ffmpeg.

    Uses ffmpeg's concat demuxer with ``-c copy`` (no decode/re-encode) so
    the operation is near-instant even for large files — typically 2-5 s for
    a 30-minute podcast vs. 2-3 minutes with pydub.
    """
    import subprocess

    kept = [s for s in segments if s.label == "keep"]
    if not kept:
        sys.exit(
            "Error: No 'keep' segments found — nothing to export.\n"
            "Try lowering --threshold or check that the script matches the recording."
        )

    # Write a temporary concat list for ffmpeg.
    concat_file = output_path + ".concat.txt"
    abs_input = os.path.abspath(input_path)
    try:
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in kept:
                f.write(f"file '{abs_input}'\n")
                f.write(f"inpoint {seg.start:.3f}\n")
                f.write(f"outpoint {seg.end:.3f}\n")

        print(f"  Exporting cleaned audio → '{output_path}'…")
        proc = subprocess.run(
            ["ffmpeg", "-y",
             "-f", "concat", "-safe", "0",
             "-i", concat_file,
             "-c", "copy",
             output_path],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg concat failed:\n" + proc.stderr.decode(errors="replace")
            )
    finally:
        try:
            os.unlink(concat_file)
        except Exception:
            pass

    print("  Export done.")


# ─────────────────────────────────────────────────────────────────────────────
# Optional: save a JSON log of every segment
# ─────────────────────────────────────────────────────────────────────────────

def save_log(segments: list[Segment], log_path: str) -> None:
    """
    Write a human-readable JSON log listing every kept and removed segment
    with timestamps and a description.

    The log is useful for reviewing the edit and debugging alignment issues.
    """
    kept    = [s for s in segments if s.label == "keep"]
    blooper = [s for s in segments if s.label == "blooper"]

    report = {
        "summary": {
            "segments_kept":    len(kept),
            "segments_removed": len(blooper),
            "total_kept_s":     round(sum(s.end - s.start for s in kept),    2),
            "total_removed_s":  round(sum(s.end - s.start for s in blooper), 2),
        },
        "segments": [
            {
                "label":       s.label,
                "start_s":     round(s.start, 3),
                "end_s":       round(s.end,   3),
                "duration_s":  round(s.end - s.start, 3),
                "note":        s.note,
            }
            for s in segments
        ],
    }

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"  Log saved → '{log_path}'")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clean_podcast",
        description=(
            "Remove podcast bloopers by aligning audio to a Word-document script.\n"
            "Uses Whisper for transcription and fuzzy matching for alignment — "
            "no cloud API required."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python clean_podcast.py --audio recording.mp3 --script script.docx --output cleaned.mp3
  python clean_podcast.py --audio raw.wav --script ep1.docx --output ep1_clean.wav --model medium
  python clean_podcast.py --audio raw.mp3 --script ep1.docx --output out.mp3 --save-log --no-crossfade
        """,
    )
    parser.add_argument(
        "--audio", required=True,
        help="Raw podcast audio file (.mp3, .wav, .m4a, …)",
    )
    parser.add_argument(
        "--script", required=True,
        help="Word document containing the intended script (.docx)",
    )
    parser.add_argument(
        "--output", required=True,
        help="Output path for the cleaned audio file (.mp3 or .wav)",
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help=(
            "Whisper model size (default: base).  "
            "Larger models are slower but more accurate for complex speech."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=70,
        metavar="0-100",
        help=(
            "Fuzzy match threshold (default: 70).  "
            "Lower values are more lenient and catch near-matches; "
            "higher values are stricter and reduce false positives."
        ),
    )
    parser.add_argument(
        "--no-crossfade",
        action="store_true",
        help="Disable the 20 ms crossfade applied between joined segments.",
    )
    parser.add_argument(
        "--save-log",
        action="store_true",
        help=(
            "Save a JSON log of every kept / removed segment alongside "
            "the output file (filename: <output>_log.json)."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ── Validate inputs ── #
    for path, flag in [(args.audio, "--audio"), (args.script, "--script")]:
        if not os.path.isfile(path):
            sys.exit(f"Error: {flag} file not found: '{path}'")

    if not (0 <= args.threshold <= 100):
        sys.exit("Error: --threshold must be between 0 and 100.")

    print("\n=== clean_podcast — Podcast Blooper Cleaner ===\n")

    # ── Step 1: Transcribe ── #
    print("Step 1/3  Transcribing audio with Whisper…")
    transcript_words = transcribe_audio(args.audio, model_size=args.model)
    if not transcript_words:
        sys.exit("Error: Whisper returned an empty transcript.  Is the audio valid?")

    # ── Step 2: Parse script ── #
    print("\nStep 2/3  Parsing Word-document script…")
    script_text = parse_script(args.script)

    # ── Step 3: Align and detect bloopers ── #
    print("\nStep 3/3  Aligning transcript to script (fuzzy matching)…")
    segments = align_and_detect_bloopers(
        transcript_words,
        script_text,
        match_threshold=args.threshold,
    )

    # ── Export cleaned audio ── #
    print("\n  Editing audio…")
    crossfade_ms = 0 if args.no_crossfade else 20
    edit_audio(args.audio, segments, args.output, crossfade_ms=crossfade_ms)

    # ── Optional JSON log ── #
    if args.save_log:
        log_path = os.path.splitext(args.output)[0] + "_log.json"
        save_log(segments, log_path)

    print(f"\n✓  Cleaned audio written to '{args.output}'\n")


if __name__ == "__main__":
    main()
