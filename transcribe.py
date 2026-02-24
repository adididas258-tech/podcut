"""
Transcribe an audio file using OpenAI Whisper and return
segment-level text with timestamps.

Requires: pip install openai-whisper
System dep: ffmpeg must be installed (apt install ffmpeg / brew install ffmpeg)
"""

import whisper
from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    start: float   # seconds
    end: float     # seconds
    text: str


def transcribe_audio(audio_path: str, model_size: str = "base") -> list[TranscriptSegment]:
    """
    Transcribe audio and return a list of timed segments.

    Args:
        audio_path: Path to the input audio file (mp3, wav, m4a, etc.)
        model_size: Whisper model to use. Options: tiny, base, small, medium, large
                    'base' balances speed and accuracy for most podcasts.

    Returns:
        List of TranscriptSegment with start/end times and text.
    """
    print(f"  Loading Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)

    print(f"  Transcribing '{audio_path}'...")
    result = model.transcribe(audio_path, word_timestamps=False, verbose=False)

    segments = []
    for seg in result["segments"]:
        segments.append(TranscriptSegment(
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
        ))

    print(f"  Transcription complete: {len(segments)} segments found.")
    return segments


def format_transcript_for_claude(segments: list[TranscriptSegment]) -> str:
    """Format transcript segments into a readable string for the Claude prompt."""
    lines = []
    for seg in segments:
        lines.append(f"[{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")
    return "\n".join(lines)
