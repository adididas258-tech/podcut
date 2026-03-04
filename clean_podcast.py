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
    pip install openai-whisper python-docx pydub rapidfuzz
    ffmpeg must be installed (apt install ffmpeg  /  brew install ffmpeg)
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

def transcribe_audio(audio_path: str, model_size: str = "base") -> list[Word]:
    """
    Run Whisper on the audio file and return every word with its timestamp.

    We request word_timestamps=True so each word gets its own start/end time.
    If the chosen model doesn't return word-level data (rare), we fall back to
    distributing each segment's time span evenly across its words.

    Args:
        audio_path:  Path to the raw audio file (.mp3, .wav, .m4a, …).
        model_size:  Whisper model to load. Larger = slower but more accurate.
                     "base" is a good default for clear podcast speech.

    Returns:
        List of Word objects ordered by time.
    """
    try:
        import whisper
    except ImportError:
        sys.exit(
            "Error: openai-whisper is not installed.\n"
            "Fix: pip install openai-whisper"
        )

    print(f"  Loading Whisper '{model_size}' model…")
    model = whisper.load_model(model_size)

    print(f"  Transcribing '{audio_path}'…")
    result = model.transcribe(audio_path, word_timestamps=True, verbose=False)

    words: list[Word] = []

    for seg in result["segments"]:
        seg_words = seg.get("words", [])

        if seg_words:
            # Happy path: Whisper returned per-word timing.
            for w in seg_words:
                raw = w["word"].strip()
                if not raw:
                    continue
                words.append(Word(
                    text=raw,
                    norm=_normalize(raw),
                    start=float(w["start"]),
                    end=float(w["end"]),
                ))
        else:
            # Fallback: distribute the segment's time evenly across its words.
            raw_words = seg["text"].strip().split()
            if not raw_words:
                continue
            seg_start = float(seg["start"])
            seg_end = float(seg["end"])
            step = (seg_end - seg_start) / len(raw_words)
            for i, raw in enumerate(raw_words):
                words.append(Word(
                    text=raw,
                    norm=_normalize(raw),
                    start=seg_start + i * step,
                    end=seg_start + (i + 1) * step,
                ))

    print(f"  Transcription complete: {len(words)} words.")
    return words


def _normalize(word: str) -> str:
    """
    Strip punctuation and lowercase a word for fuzzy comparison.
    Keeps letters, digits, and apostrophes (contractions like "don't").
    """
    return re.sub(r"[^a-z0-9']", "", word.lower())


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Parse the Word-document script
# ─────────────────────────────────────────────────────────────────────────────

def parse_script(docx_path: str) -> str:
    """
    Extract plain narration text from a .docx file.

    All character formatting (bold, italic, font size) is ignored — only the
    raw text matters.  Paragraphs whose every run is highlighted with a marker
    colour are treated as stage directions / production notes and skipped so
    they don't pollute the text the audio is compared against.

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
            if not is_highlighted:
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

    # --- Phase A: find all candidate windows for each sentence ------------- #
    print("  Scanning transcript for sentence matches…")
    all_candidates: list[list[tuple[int, int, float]]] = []
    for sentence in script_sentences:
        sent_words = [_normalize(w) for w in sentence.split() if _normalize(w)]
        if len(sent_words) < 2:
            all_candidates.append([])  # too short to be a reliable anchor
            continue
        candidates = _find_all_windows(sent_words, norm_transcript, match_threshold)
        all_candidates.append(candidates)

    # --- Phase B: greedy monotone path (last clean take wins) -------------- #
    print("  Selecting best takes (restarts handled — last clean take wins)…")
    chosen_matches = _pick_best_path(all_candidates)

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
) -> list[tuple[int, int, float]]:
    """
    Slide a window of len(sent_words) words across the transcript and return
    every position that scores >= threshold.

    A small slack (±n/5 extra words) is tried at each position so that filler
    words like "um" or "uh" inserted between script words don't cause a miss.

    Returns a list of (start_idx, end_idx, score) tuples, sorted by start_idx.
    """
    from rapidfuzz import fuzz

    n = len(sent_words)
    sent_str = " ".join(sent_words)
    # Maximum extra words to tolerate (fillers, hesitations).
    slack = max(2, n // 5)
    matches: list[tuple[int, int, float]] = []

    for i in range(len(norm_transcript) - n + 1):
        best_score = 0.0
        best_end = i + n

        # Try the exact window size and slightly larger windows.
        for extra in range(0, slack + 1):
            end = i + n + extra
            if end > len(norm_transcript):
                break
            window_str = " ".join(norm_transcript[i:end])
            score = fuzz.ratio(sent_str, window_str)
            if score > best_score:
                best_score = score
                best_end = end

        if best_score >= threshold:
            matches.append((i, best_end, best_score))

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
    crossfade_ms: int = 20,
) -> None:
    """
    Extract all 'keep' segments from the source audio and concatenate them
    into a single clean output file.

    A short crossfade (default 20 ms) is applied at each cut point to prevent
    audible clicks where segments join.  Pass crossfade_ms=0 to disable.

    Args:
        input_path:   Path to the raw source audio file.
        segments:     Ordered list of Segment objects from align_and_detect_bloopers.
        output_path:  Where to write the cleaned audio.
        crossfade_ms: Duration of the crossfade in milliseconds.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        sys.exit(
            "Error: pydub is not installed.\n"
            "Fix: pip install pydub"
        )

    print(f"  Loading audio from '{input_path}'…")
    audio = AudioSegment.from_file(input_path)
    total_ms = len(audio)
    print(f"  Total source duration: {total_ms / 1000:.1f}s")

    kept_segments = [s for s in segments if s.label == "keep"]
    if not kept_segments:
        sys.exit(
            "Error: No 'keep' segments found — nothing to export.\n"
            "Try lowering --threshold or check that the script matches the recording."
        )

    result = AudioSegment.empty()

    for seg in kept_segments:
        # Convert seconds to milliseconds, clamp to valid range.
        start_ms = max(0,        int(seg.start * 1000))
        end_ms   = min(total_ms, int(seg.end   * 1000))

        if end_ms <= start_ms:
            continue  # zero-length or inverted segment — skip

        chunk = audio[start_ms:end_ms]

        if len(result) > 0 and crossfade_ms > 0:
            # Clamp crossfade to the shorter of the two clips.
            cf = min(crossfade_ms, len(result), len(chunk))
            result = result.append(chunk, crossfade=cf)
        else:
            result += chunk

    # Infer format from the output file extension.
    ext = os.path.splitext(output_path)[1].lstrip(".").lower() or "mp3"
    export_kwargs: dict = {"format": ext}
    if ext == "mp3":
        export_kwargs["bitrate"] = "192k"

    print(f"  Exporting cleaned audio → '{output_path}' ({ext.upper()})…")
    result.export(output_path, **export_kwargs)

    cleaned_s = len(result) / 1000.0
    removed_s = total_ms / 1000.0 - cleaned_s
    print(
        f"  Export done.  "
        f"Cleaned duration: {cleaned_s:.1f}s  |  "
        f"Removed: {removed_s:.1f}s of bloopers"
    )


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
