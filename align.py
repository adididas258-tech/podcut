"""
Use Claude to compare the audio transcript against the script,
identify bloopers, and return which time segments to keep.

Requires: pip install anthropic pydantic
ANTHROPIC_API_KEY must be set in environment.
"""

import json
import anthropic
from pydantic import BaseModel

from transcribe import TranscriptSegment, format_transcript_for_claude


# ---------------------------------------------------------------------------
# Pydantic models for structured output from Claude
# ---------------------------------------------------------------------------

class KeepSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    script_excerpt: str   # Brief note about what script line this covers


class BlooperSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    reason: str           # Why this was flagged (false start, repeat, off-script, etc.)


class AudioAnalysis(BaseModel):
    summary: str
    segments_to_keep: list[KeepSegment]
    bloopers_removed: list[BlooperSegment]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert podcast audio editor. Your job is to analyse a raw recording of a podcast host reading from a script and produce a clean edit by identifying bloopers.

DEFINITIONS:
- BLOOPER: any portion of the recording where the host deviated from the script. This includes false starts ("wait, let me restart"), stumbles with significant repetition, off-script tangents, or sections where the host explicitly re-records a line.
- KEEP: portions where the host is correctly reading the intended script text.

RULES:
1. If the host repeated a sentence or paragraph and eventually got it right, keep ONLY the best final take.
2. If the host added brief natural filler ("um", "uh") but stayed on-script, keep that segment — do not over-edit.
3. The segments_to_keep list must be ordered chronologically by start_seconds.
4. Cover the entire recording: every second must be either kept or removed.
5. Use the script as ground truth for what should be in the final audio.
"""

USER_PROMPT_TEMPLATE = """Please analyse this podcast recording and return which segments to keep.

--- SCRIPT (intended text) ---
{script}

--- TRANSCRIPT WITH TIMESTAMPS ---
{transcript}

Return a JSON object matching this schema exactly:
{{
  "summary": "<brief description of what edits were made>",
  "segments_to_keep": [
    {{"start_seconds": <float>, "end_seconds": <float>, "script_excerpt": "<which part of the script this covers>"}}
  ],
  "bloopers_removed": [
    {{"start_seconds": <float>, "end_seconds": <float>, "reason": "<why removed>"}}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def detect_bloopers(
    segments: list[TranscriptSegment],
    script_text: str,
) -> AudioAnalysis:
    """
    Call Claude to compare the transcript with the script and identify bloopers.

    Args:
        segments: Whisper transcript segments with timestamps.
        script_text: Full intended script text from the Word document.

    Returns:
        AudioAnalysis with segments_to_keep and bloopers_removed.
    """
    client = anthropic.Anthropic()

    transcript_text = format_transcript_for_claude(segments)
    user_message = USER_PROMPT_TEMPLATE.format(
        script=script_text,
        transcript=transcript_text,
    )

    print("  Sending transcript to Claude for analysis...")

    # Use streaming + get_final_message to handle potentially large payloads
    # without risking HTTP timeouts.
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        response = stream.get_final_message()

    # Extract the text block (thinking blocks may precede it)
    raw_text = next(
        block.text for block in response.content if block.type == "text"
    )

    # Strip any accidental markdown fencing Claude might add
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = "\n".join(clean.split("\n")[1:])
    if clean.endswith("```"):
        clean = "\n".join(clean.split("\n")[:-1])

    data = json.loads(clean)
    analysis = AudioAnalysis(**data)

    print(f"  Analysis complete:")
    print(f"    Segments to keep : {len(analysis.segments_to_keep)}")
    print(f"    Bloopers removed : {len(analysis.bloopers_removed)}")
    if analysis.bloopers_removed:
        total_blooper_s = sum(
            b.end_seconds - b.start_seconds for b in analysis.bloopers_removed
        )
        print(f"    Total blooper time: {total_blooper_s:.1f}s")

    return analysis
