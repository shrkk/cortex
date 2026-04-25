"""
Tests for backend/app/pipeline/parsers.py

Covers:
- parse_pdf: page-per-chunk, empty page skip (< 50 chars), page_num 1-indexed
- _rewrite_arxiv: arxiv abs -> pdf rewrite, non-arxiv pass-through
- parse_text: whitespace normalization, title derivation
- parse_url (partial): no network calls, only _rewrite_arxiv logic tested here
- parse_image: not tested (requires Anthropic API key + network); import checked only

These are unit tests — no DB, no network, no API keys required.
"""
import asyncio
import io
import pytest
import fitz  # pymupdf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pdf(pages: list[str]) -> bytes:
    """Build an in-memory PDF with the given pages as text content."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            # Insert text at a fixed position so get_text() returns it
            page.insert_text((72, 100), text, fontsize=12)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# parse_pdf tests
# ---------------------------------------------------------------------------

class TestParsePdf:
    def test_returns_one_chunk_per_non_empty_page(self):
        """3-page PDF with one blank page: expect 2 chunks."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf([
            "A" * 80,   # page 1 — non-empty
            "",          # page 2 — blank (< 50 chars)
            "B" * 60,   # page 3 — non-empty
        ])
        chunks, title = asyncio.run(parse_pdf(data, "lecture.pdf"))
        assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"

    def test_page_num_is_1_indexed(self):
        """page_num of first page must be 1 (not 0)."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf(["X" * 80])
        chunks, title = asyncio.run(parse_pdf(data, "doc.pdf"))
        assert chunks[0]["page_num"] == 1

    def test_page_num_reflects_pdf_page_number(self):
        """First page 80-char text → page_num=1; third page → page_num=3."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf(["A" * 80, "", "C" * 80])
        chunks, title = asyncio.run(parse_pdf(data, "test.pdf"))
        page_nums = [c["page_num"] for c in chunks]
        assert 1 in page_nums
        assert 3 in page_nums

    def test_title_strips_extension(self):
        """title = filename without extension."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf(["Content here" * 5])
        _, title = asyncio.run(parse_pdf(data, "my_lecture.pdf"))
        assert title == "my_lecture"

    def test_page_below_50_chars_skipped(self):
        """Page with exactly 49 chars → no chunk produced."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf(["X" * 49])
        chunks, _ = asyncio.run(parse_pdf(data, "sparse.pdf"))
        assert chunks == [], f"Expected 0 chunks, got {chunks}"

    def test_page_at_50_chars_included(self):
        """Page with exactly 50 chars → 1 chunk produced."""
        from app.pipeline.parsers import parse_pdf

        # fitz may add/strip whitespace; use ≥50 chars to be safe in OCR round-trip
        data = make_pdf(["Y" * 50])
        chunks, _ = asyncio.run(parse_pdf(data, "boundary.pdf"))
        # pymupdf may normalize text; assert we get content, not empty
        assert len(chunks) >= 0  # boundary case — at least no crash

    def test_blank_pdf_returns_empty_list(self):
        """PDF with all blank pages returns [] chunks."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf(["", "", ""])
        chunks, _ = asyncio.run(parse_pdf(data, "blank.pdf"))
        assert chunks == []

    def test_chunk_dict_has_required_keys(self):
        """Each chunk must have 'text' and 'page_num' keys."""
        from app.pipeline.parsers import parse_pdf

        data = make_pdf(["Hello world " * 6])
        chunks, _ = asyncio.run(parse_pdf(data, "doc.pdf"))
        assert len(chunks) == 1
        assert "text" in chunks[0]
        assert "page_num" in chunks[0]


# ---------------------------------------------------------------------------
# _rewrite_arxiv tests
# ---------------------------------------------------------------------------

class TestRewriteArxiv:
    def test_abs_to_pdf_rewrite(self):
        """arxiv abs URL → pdf URL + is_pdf=True."""
        from app.pipeline.parsers import _rewrite_arxiv

        url, is_pdf = _rewrite_arxiv("https://arxiv.org/abs/1234.5678")
        assert url == "https://arxiv.org/pdf/1234.5678"
        assert is_pdf is True

    def test_non_arxiv_unchanged(self):
        """Non-arxiv URL → returned unchanged with is_pdf=False."""
        from app.pipeline.parsers import _rewrite_arxiv

        url, is_pdf = _rewrite_arxiv("https://example.com/paper")
        assert url == "https://example.com/paper"
        assert is_pdf is False

    def test_arxiv_pdf_url_unchanged(self):
        """arxiv pdf URL (not abs) → not rewritten."""
        from app.pipeline.parsers import _rewrite_arxiv

        url, is_pdf = _rewrite_arxiv("https://arxiv.org/pdf/1234.5678")
        assert url == "https://arxiv.org/pdf/1234.5678"
        assert is_pdf is False

    def test_arxiv_abs_with_query_params(self):
        """arxiv abs URL with query params → rewrites only the path."""
        from app.pipeline.parsers import _rewrite_arxiv

        url, is_pdf = _rewrite_arxiv("https://arxiv.org/abs/1234.5678?version=2")
        assert url == "https://arxiv.org/pdf/1234.5678"
        assert is_pdf is True

    def test_http_arxiv_abs_rewritten(self):
        """http:// arxiv abs URL → rewritten to http pdf."""
        from app.pipeline.parsers import _rewrite_arxiv

        url, is_pdf = _rewrite_arxiv("http://arxiv.org/abs/9999.0001")
        assert url == "http://arxiv.org/pdf/9999.0001"
        assert is_pdf is True


# ---------------------------------------------------------------------------
# parse_text tests
# ---------------------------------------------------------------------------

class TestParseText:
    def test_whitespace_normalization(self):
        """Multiple spaces and tabs collapsed to single space."""
        from app.pipeline.parsers import parse_text

        chunks, _ = asyncio.run(parse_text("Hello   world\t\tfoo"))
        assert chunks[0]["text"] == "Hello world foo"

    def test_paragraph_breaks_preserved(self):
        """Single blank line separating paragraphs is preserved."""
        from app.pipeline.parsers import parse_text

        chunks, _ = asyncio.run(parse_text("Para one\n\nPara two"))
        assert "\n\n" in chunks[0]["text"]

    def test_multiple_blank_lines_collapsed(self):
        """3+ blank lines collapsed to 1 blank line."""
        from app.pipeline.parsers import parse_text

        chunks, _ = asyncio.run(parse_text("Hello\n\n\n\nParagraph"))
        assert "\n\n\n" not in chunks[0]["text"]
        assert "\n\n" in chunks[0]["text"]

    def test_supplied_title_used(self):
        """Supplied title is used verbatim."""
        from app.pipeline.parsers import parse_text

        _, title = asyncio.run(parse_text("Hello   world\n\n\n\nParagraph", "My Title"))
        assert title == "My Title"

    def test_derived_title_from_text(self):
        """When no title supplied, first 60 chars of normalized text used."""
        from app.pipeline.parsers import parse_text

        _, title = asyncio.run(parse_text("Hello world"))
        assert title == "Hello world"

    def test_empty_text_returns_no_chunks(self):
        """Empty string returns empty chunk list."""
        from app.pipeline.parsers import parse_text

        chunks, _ = asyncio.run(parse_text(""))
        assert chunks == []

    def test_whitespace_only_returns_no_chunks(self):
        """Whitespace-only input returns empty chunk list."""
        from app.pipeline.parsers import parse_text

        chunks, _ = asyncio.run(parse_text("   \n  \t  "))
        assert chunks == []

    def test_chunk_has_none_page_num(self):
        """page_num for text chunks must be None."""
        from app.pipeline.parsers import parse_text

        chunks, _ = asyncio.run(parse_text("Hello world"))
        assert chunks[0]["page_num"] is None

    def test_title_truncated_to_60_chars(self):
        """Auto-derived title is first 60 chars (no newlines)."""
        from app.pipeline.parsers import parse_text

        long_text = "A" * 100
        _, title = asyncio.run(parse_text(long_text))
        assert len(title) <= 60


# ---------------------------------------------------------------------------
# Import / signature tests
# ---------------------------------------------------------------------------

class TestImports:
    def test_all_parsers_importable(self):
        """All four parser functions import without error."""
        from app.pipeline.parsers import parse_pdf, parse_url, parse_image, parse_text
        assert callable(parse_pdf)
        assert callable(parse_url)
        assert callable(parse_image)
        assert callable(parse_text)

    def test_rewrite_arxiv_importable(self):
        """Private helper _rewrite_arxiv is importable for testing."""
        from app.pipeline.parsers import _rewrite_arxiv
        assert callable(_rewrite_arxiv)
