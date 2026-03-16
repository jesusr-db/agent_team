"""Pure-Python text cleaning and chunking helpers.

This module contains no Spark or DLT dependencies so it can be unit-tested
locally.  The DLT table definition in chunk_docs.py calls these helpers.

Chunking strategy (from domain playbook):
  - Target size : 512 tokens (~2000 characters)
  - Overlap     : 64 tokens  (~250 characters)
  - Section-aware: prefer splitting at Markdown heading boundaries
"""

import json
import re
import uuid

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHUNK_SIZE_CHARS = 2000  # ~512 tokens
OVERLAP_CHARS = 250  # ~64 tokens
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def clean_text(text: str) -> str:
    """Normalise whitespace and strip control characters."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_sections(text: str) -> list[tuple[list[str], str]]:
    """Split text on Markdown headings, returning (heading_hierarchy, body) pairs."""
    parts: list[tuple[list[str], str]] = []
    current_headings: list[str] = []
    last_end = 0

    for match in HEADING_RE.finditer(text):
        # Flush preceding body
        body = text[last_end : match.start()].strip()
        if body:
            parts.append((list(current_headings), body))

        level = len(match.group(1))
        heading_text = match.group(2).strip()

        # Trim heading stack to current level and push
        current_headings = current_headings[: level - 1]
        current_headings.append(heading_text)

        last_end = match.end()

    # Remaining text after last heading
    tail = text[last_end:].strip()
    if tail:
        parts.append((list(current_headings), tail))

    if not parts:
        parts.append(([], text))

    return parts


def split_body(body: str, size: int, overlap: int) -> list[str]:
    """Split a body string into overlapping chunks, preferring sentence boundaries."""
    if len(body) <= size:
        return [body]

    chunks: list[str] = []
    start = 0
    while start < len(body):
        end = start + size
        if end < len(body):
            # Try to break at a sentence boundary
            boundary = body.rfind(". ", start, end)
            if boundary > start:
                end = boundary + 1  # include the period
        chunk = body[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(body) else len(body)
    return chunks


def chunk_document(doc_path: str, doc_content: str) -> list[dict]:
    """Return a list of chunk dicts for one document."""
    cleaned = clean_text(doc_content)
    sections = split_into_sections(cleaned)

    chunks: list[dict] = []
    chunk_idx = 0

    for headings, body in sections:
        sub_chunks = split_body(body, CHUNK_SIZE_CHARS, OVERLAP_CHARS)
        for text in sub_chunks:
            title = headings[0] if headings else ""
            section = headings[-1] if headings else ""
            metadata = json.dumps(
                {"title": title, "section": section, "headings": headings}
            )
            chunks.append(
                {
                    "chunk_id": str(uuid.uuid4()),
                    "doc_source": doc_path,
                    "chunk_text": text,
                    "chunk_index": chunk_idx,
                    "metadata": metadata,
                }
            )
            chunk_idx += 1

    return chunks
