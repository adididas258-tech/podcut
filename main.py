#!/usr/bin/env python3
"""
podcut — Podcast audio cleanup tool

Automatically removes bloopers from a podcast recording by comparing it
against the intended script (a Word .docx file).

Usage:
    python main.py recording.mp3 script.docx cleaned.mp3

Requirements:
    pip install -r requirements.txt
    ffmpeg must be installed (apt install ffmpeg  /  brew install ffmpeg)
    ANTHROPIC_API_KEY must be set in your environment.
"""

import argparse
import os
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="podcut",
        description="Remove podcast bloopers by aligning audio to a Word script.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py episode1.mp3 episode1_script.docx episode1_clean.mp3
  python main.py raw.wav script.docx final.wav --whisper-model medium
  python main.py raw.mp3 script.docx out.mp3 --no-crossfade --save-report
        """,
    )
    parser.add_argument("audio", help="Raw podcast audio file (mp3, wav, m4a, …)")
    parser.add_argument("script", help="Word document with the intended script (.docx)")
    parser.add_argument("output", help="Output path for the cleaned audio file")
    parser.add_argument(
        "--whisper-model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Larger = more accurate but slower.",
    )
    parser.add_argument(
        "--no-crossfade",
        action="store_true",
        help="Disable the short crossfade between kept segments.",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save a JSON report of kept/removed segments alongside the output file.",
    )
    return parser.parse_args()


def check_env() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(
            "Error: ANTHROPIC_API_KEY is not set.\n"
            "Export your API key:  export ANTHROPIC_API_KEY=sk-ant-..."
        )


def main() -> None:
    args = parse_args()
    check_env()

    # Validate inputs
    for path, label in [(args.audio, "audio"), (args.script, "script")]:
        if not os.path.isfile(path):
            sys.exit(f"Error: {label} file not found: '{path}'")

    print("\n=== podcut — Podcast Blooper Cleaner ===\n")

    # Step 1 — Transcribe audio
    print("Step 1/3  Transcribing audio with Whisper…")
    from transcribe import transcribe_audio
    segments = transcribe_audio(args.audio, model_size=args.whisper_model)

    if not segments:
        sys.exit("Error: Whisper produced an empty transcript. Is the audio file valid?")

    # Step 2 — Parse script
    print("\nStep 2/3  Parsing script…")
    from parse_script import parse_word_doc
    script_text = parse_word_doc(args.script)

    # Step 3a — Claude analysis
    print("\nStep 3/3  Analysing with Claude (this may take a moment)…")
    from align import detect_bloopers
    analysis = detect_bloopers(segments, script_text)

    print(f"\n  Claude's summary:\n  {analysis.summary}\n")

    if not analysis.segments_to_keep:
        sys.exit("Error: Claude returned no segments to keep. Check your input files.")

    # Step 3b — Edit audio
    from edit_audio import edit_audio
    crossfade_ms = 0 if args.no_crossfade else 20
    edit_audio(
        input_path=args.audio,
        segments_to_keep=analysis.segments_to_keep,
        output_path=args.output,
        crossfade_ms=crossfade_ms,
    )

    # Optional: save JSON report
    if args.save_report:
        import json
        report_path = os.path.splitext(args.output)[0] + "_report.json"
        report = {
            "summary": analysis.summary,
            "segments_kept": [
                {
                    "start_s": s.start_seconds,
                    "end_s": s.end_seconds,
                    "script_excerpt": s.script_excerpt,
                }
                for s in analysis.segments_to_keep
            ],
            "bloopers_removed": [
                {
                    "start_s": b.start_seconds,
                    "end_s": b.end_seconds,
                    "reason": b.reason,
                }
                for b in analysis.bloopers_removed
            ],
        }
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Report saved to '{report_path}'")

    print(f"\n✓  Cleaned audio written to '{args.output}'\n")


if __name__ == "__main__":
    main()
