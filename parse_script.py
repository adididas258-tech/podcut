"""
Parse a Word (.docx) document and extract the script text.
Each paragraph becomes a line. Empty paragraphs are skipped.

Requires: pip install python-docx
"""

import docx


def parse_word_doc(docx_path: str) -> str:
    """
    Extract plain text from a Word document.

    Args:
        docx_path: Path to the .docx file.

    Returns:
        Full script text as a single string, paragraphs separated by newlines.
    """
    doc = docx.Document(docx_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ValueError(f"No text found in '{docx_path}'. Is the file empty?")

    script = "\n".join(paragraphs)
    print(f"  Script parsed: {len(paragraphs)} paragraph(s), {len(script.split())} words.")
    return script
