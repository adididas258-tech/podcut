"""
Slice an audio file, keeping only the approved segments, and export
the result as a clean recording.

Requires: pip install pydub
System dep: ffmpeg (apt install ffmpeg / brew install ffmpeg)
"""

import os
from pydub import AudioSegment

from align import KeepSegment


def edit_audio(
    input_path: str,
    segments_to_keep: list[KeepSegment],
    output_path: str,
    crossfade_ms: int = 20,
) -> None:
    """
    Extract and concatenate approved segments from the audio file.

    Args:
        input_path:      Path to the raw podcast audio file.
        segments_to_keep: Ordered list of (start_seconds, end_seconds) segments
                          returned by Claude.
        output_path:     Where to write the cleaned audio.
        crossfade_ms:    Short crossfade between segments to avoid click artefacts.
                         Set to 0 to disable.
    """
    if not segments_to_keep:
        raise ValueError("No segments to keep — nothing would be written.")

    print(f"  Loading audio from '{input_path}'...")
    audio = AudioSegment.from_file(input_path)
    total_duration_s = len(audio) / 1000.0
    print(f"  Total audio duration: {total_duration_s:.1f}s")

    result = AudioSegment.empty()

    for i, seg in enumerate(segments_to_keep):
        start_ms = int(seg.start_seconds * 1000)
        end_ms = int(seg.end_seconds * 1000)

        # Guard against out-of-bounds slices
        start_ms = max(0, start_ms)
        end_ms = min(len(audio), end_ms)

        if end_ms <= start_ms:
            print(f"  Warning: segment {i} has zero/negative length, skipping.")
            continue

        chunk = audio[start_ms:end_ms]

        if result and crossfade_ms > 0:
            # Brief crossfade to smooth cut points
            cf = min(crossfade_ms, len(result), len(chunk))
            result = result.append(chunk, crossfade=cf)
        else:
            result += chunk

    # Determine output format from file extension (mp3, wav, m4a, flac, …)
    ext = os.path.splitext(output_path)[1].lstrip(".").lower() or "mp3"
    export_kwargs = {"format": ext}
    if ext == "mp3":
        export_kwargs["bitrate"] = "192k"

    print(f"  Exporting cleaned audio to '{output_path}'...")
    result.export(output_path, **export_kwargs)

    cleaned_duration_s = len(result) / 1000.0
    removed_s = total_duration_s - cleaned_duration_s
    print(f"  Done. Cleaned duration: {cleaned_duration_s:.1f}s  "
          f"(removed {removed_s:.1f}s of bloopers)")
