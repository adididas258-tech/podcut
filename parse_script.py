"""
Parse a Word (.docx) document and extract the script text.
Each paragraph becomes a line. Empty paragraphs are skipped.

Text highlighted with a marker colour (yellow, green, cyan, etc.) is
considered a production note / stage direction and is EXCLUDED from the
narration text that is compared against the audio recording.

Requires: pip install python-docx
"""

import docx
from docx.enum.text import WD_COLOR_INDEX


def _is_highlighted(run) -> bool:
    """Return True if the run has any marker highlight applied."""
    color = run.font.highlight_color
    # None and WD_COLOR_INDEX.AUTO both mean "no highlight"
    return color is not None and color != WD_COLOR_INDEX.AUTO


def _paragraph_narration_text(paragraph) -> str:
    """
    Return only the non-highlighted runs of a paragraph joined together.
    Highlighted runs (marker colour) are treated as stage directions and skipped.
    """
    parts = [run.text for run in paragraph.runs if not _is_highlighted(run)]
    return "".join(parts).strip()


def parse_word_doc(docx_path: str) -> str:
    """
    Extract narration text from a Word document, ignoring highlighted passages.

    Highlighted text (any marker colour) is assumed to be a production note
    or stage direction — it is silently skipped so that it does not appear in
    the script that gets compared to the audio transcript.

    Args:
        docx_path: Path to the .docx file.

    Returns:
        Full narration text as a single string, paragraphs separated by newlines.
    """
    doc = docx.Document(docx_path)

    paragraphs = []
    skipped_highlighted_words = 0

    for p in doc.paragraphs:
        narration = _paragraph_narration_text(p)

        # Count how many highlighted words were stripped from this paragraph
        full_text = p.text.strip()
        if full_text and not narration:
            # Entire paragraph was highlighted — skip silently (stage direction)
            highlighted_words = len(full_text.split())
            skipped_highlighted_words += highlighted_words
            continue

        if narration:
            paragraphs.append(narration)
            # Tally any partial highlighting within kept paragraphs
            removed = len(full_text.split()) - len(narration.split())
            if removed > 0:
                skipped_highlighted_words += removed

    if not paragraphs:
        raise ValueError(f"No narration text found in '{docx_path}'. "
                         "Is the file empty, or is all text highlighted?")

    script = "\n".join(paragraphs)
    print(f"  Script parsed: {len(paragraphs)} paragraph(s), "
          f"{len(script.split())} narration words "
          f"({skipped_highlighted_words} highlighted words excluded).")
    return script
