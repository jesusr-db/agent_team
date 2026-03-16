"""Unit tests for the document chunking logic.

These tests exercise the pure-Python helpers in chunking.py without
requiring a Spark session, so they run quickly in CI.
"""

import json
import sys
import os

# Ensure the src package is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"),
)

from transformations.chunking import (
    CHUNK_SIZE_CHARS,
    OVERLAP_CHARS,
    clean_text,
    split_body,
    split_into_sections,
    chunk_document,
)


# --------------------------------------------------------------------------- #
# clean_text
# --------------------------------------------------------------------------- #


class TestCleanText:
    def test_normalises_crlf(self):
        assert "\n" in clean_text("a\r\nb")
        assert "\r" not in clean_text("a\r\nb")

    def test_collapses_blank_lines(self):
        result = clean_text("a\n\n\n\nb")
        assert result == "a\n\nb"

    def test_collapses_spaces(self):
        result = clean_text("a   b\t\tc")
        assert result == "a b c"

    def test_strips_leading_trailing(self):
        assert clean_text("  hello  ") == "hello"


# --------------------------------------------------------------------------- #
# split_into_sections
# --------------------------------------------------------------------------- #


class TestSplitIntoSections:
    def test_no_headings(self):
        sections = split_into_sections("just plain text")
        assert len(sections) == 1
        assert sections[0][1] == "just plain text"

    def test_single_heading(self):
        text = "# Title\nSome body text."
        sections = split_into_sections(text)
        assert len(sections) == 1
        headings, body = sections[0]
        assert headings == ["Title"]
        assert body == "Some body text."

    def test_nested_headings(self):
        text = "# Top\n\nbody1\n\n## Sub\n\nbody2"
        sections = split_into_sections(text)
        assert len(sections) == 2
        assert sections[0][0] == ["Top"]
        assert sections[1][0] == ["Top", "Sub"]

    def test_heading_level_reset(self):
        text = "# A\n\nbody a\n\n## B\n\nbody b\n\n# C\n\nbody c"
        sections = split_into_sections(text)
        assert len(sections) == 3
        # When we hit "# C" the heading stack resets
        assert sections[2][0] == ["C"]


# --------------------------------------------------------------------------- #
# split_body
# --------------------------------------------------------------------------- #


class TestSplitBody:
    def test_short_body_single_chunk(self):
        text = "Short text."
        result = split_body(text, CHUNK_SIZE_CHARS, OVERLAP_CHARS)
        assert result == [text]

    def test_long_body_multiple_chunks(self):
        # Create a body larger than CHUNK_SIZE_CHARS
        sentence = "This is a sentence with enough words to be meaningful. "
        text = sentence * 100  # ~5500 chars
        chunks = split_body(text, CHUNK_SIZE_CHARS, OVERLAP_CHARS)
        assert len(chunks) > 1

    def test_overlap_exists(self):
        sentence = "Word " * 500  # 2500 chars
        chunks = split_body(sentence, CHUNK_SIZE_CHARS, OVERLAP_CHARS)
        if len(chunks) >= 2:
            # The end of chunk 0 should overlap with the start of chunk 1
            tail_of_first = chunks[0][-OVERLAP_CHARS:]
            assert tail_of_first in chunks[1]


# --------------------------------------------------------------------------- #
# chunk_document (end-to-end)
# --------------------------------------------------------------------------- #


class TestChunkDocument:
    def test_basic_document(self):
        doc = "# Getting Started\n\nWelcome to the project.\n\n## Installation\n\nRun pip install."
        result = chunk_document("docs/readme.md", doc)

        assert len(result) >= 1
        first = result[0]
        assert first["doc_source"] == "docs/readme.md"
        assert first["chunk_index"] == 0
        assert first["chunk_text"]

        meta = json.loads(first["metadata"])
        assert "headings" in meta

    def test_chunk_id_uniqueness(self):
        doc = "# Title\n\nBody text.\n\n## Section\n\nMore text."
        result = chunk_document("test.md", doc)
        ids = [c["chunk_id"] for c in result]
        assert len(ids) == len(set(ids)), "chunk_id values must be unique"

    def test_large_document_produces_multiple_chunks(self):
        # A document with a single section larger than CHUNK_SIZE_CHARS
        body = "This is a test sentence for chunking. " * 200
        doc = f"# Big Section\n\n{body}"
        result = chunk_document("big.md", doc)
        assert len(result) > 1, "Large sections should produce multiple chunks"

    def test_metadata_structure(self):
        doc = "# Top\n\n## Sub\n\nContent here."
        result = chunk_document("meta.md", doc)
        for chunk in result:
            meta = json.loads(chunk["metadata"])
            assert "title" in meta
            assert "section" in meta
            assert "headings" in meta
            assert isinstance(meta["headings"], list)

    def test_empty_document(self):
        result = chunk_document("empty.md", "")
        # Should produce at least one (possibly empty) chunk or handle gracefully
        assert isinstance(result, list)
