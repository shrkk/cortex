"""
Cortex content parsers.

Each function returns (chunks: list[dict], title: str).
Chunks are dicts with keys: text (str), page_num (int|None).
Parsers are stateless — no DB access, no session.
"""
import base64
import re
from io import BytesIO

import httpx
import trafilatura
import fitz  # pymupdf

from app.core.config import settings


# ---------------------------------------------------------------------------
# PDF parser (PARSE-01)
# ---------------------------------------------------------------------------

async def parse_pdf(data: bytes, filename: str) -> tuple[list[dict], str]:
    """Parse PDF bytes page-by-page. Returns one chunk per non-empty page.

    Empty/near-empty pages (< 50 chars after strip) are skipped (D-09).
    page_num is 1-indexed.
    """
    title = filename.rsplit(".", 1)[0]  # strip extension
    doc = fitz.open(stream=data, filetype="pdf")
    chunks: list[dict] = []
    for page in doc:
        text = page.get_text().strip()
        if len(text) < 50:
            continue  # skip blank / title pages (D-09)
        chunks.append({"text": text, "page_num": page.number + 1})
    doc.close()
    return chunks, title


# ---------------------------------------------------------------------------
# URL parser (PARSE-03 + PARSE-04 arXiv rewrite)
# ---------------------------------------------------------------------------

_ARXIV_ABS = re.compile(r"(https?://arxiv\.org)/abs/(.+?)(?:\?|$)")


def _rewrite_arxiv(url: str) -> tuple[str, bool]:
    """Rewrite arxiv.org/abs/XXXX to arxiv.org/pdf/XXXX if applicable.

    Returns (final_url, is_pdf).
    Only rewrites arxiv.org/abs/ patterns — all other URLs are left unchanged.
    """
    m = _ARXIV_ABS.match(url)
    if m:
        return f"{m.group(1)}/pdf/{m.group(2)}", True
    return url, False


async def parse_url(url: str) -> tuple[list[dict], str]:
    """Fetch a URL and extract text content.

    arXiv abs/ links are rewritten to pdf/ and routed to parse_pdf (PARSE-04).
    All other URLs are fetched and extracted with trafilatura (PARSE-03).
    Timeout: 10 seconds (PARSE-03).
    """
    final_url, is_arxiv_pdf = _rewrite_arxiv(url)

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
    ) as client:
        response = await client.get(final_url)
        response.raise_for_status()
        content = response.content

    if is_arxiv_pdf:
        # Route to PDF parser — arxiv rewrite gave us a PDF URL
        filename = final_url.rstrip("/").split("/")[-1] + ".pdf"
        return await parse_pdf(content, filename)

    # HTML path: extract with trafilatura
    raw_html = content.decode("utf-8", errors="replace")
    text = trafilatura.extract(raw_html) or ""
    text = text.strip()

    # Extract title from <title> tag (PARSE-03)
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", raw_html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else url

    if len(text) < 50:
        # Fallback: use the raw text if trafilatura extracts nothing meaningful
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = re.sub(r"\s+", " ", text).strip()

    chunks = [{"text": text, "page_num": None}] if text else []
    return chunks, title


# ---------------------------------------------------------------------------
# Image parser — Claude vision OCR (PARSE-02)
# ---------------------------------------------------------------------------

async def parse_image(data: bytes, filename: str) -> tuple[list[dict], str]:
    """Send image to Claude claude-sonnet-4-6 vision for OCR.

    Returns verbatim markdown output — text, LaTeX equations, diagram descriptions (D-10).
    Title = "Image: " + first 60 chars of OCR text.
    """
    import anthropic  # lazy import — only needed when image is processed

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Determine MIME type from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "webp": "image/webp", "heic": "image/heic"}
    media_type = mime_map.get(ext, "image/png")

    b64 = base64.standard_b64encode(data).decode()

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe this image verbatim as Markdown. "
                            "Render equations as LaTeX (inline $...$ or display $$...$$). "
                            "Describe diagrams in square brackets. "
                            "Output only the transcription — no commentary."
                        ),
                    },
                ],
            }
        ],
    )

    ocr_text = message.content[0].text if message.content else ""
    title = "Image: " + ocr_text[:60].replace("\n", " ")
    chunks = [{"text": ocr_text, "page_num": None}] if ocr_text.strip() else []
    return chunks, title


# ---------------------------------------------------------------------------
# Text parser (PARSE-05)
# ---------------------------------------------------------------------------

async def parse_text(text: str, title: str | None = None) -> tuple[list[dict], str]:
    """Normalize whitespace and derive title.

    title = supplied title, or first 60 chars of normalized text.
    Returns a single chunk containing the full normalized text.
    """
    # Collapse runs of whitespace (multiple spaces, tabs) but preserve paragraph breaks
    normalized = re.sub(r"[^\S\n]+", " ", text).strip()
    # Normalize multiple blank lines to a single blank line
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    if not title:
        title = normalized[:60].replace("\n", " ")

    chunks = [{"text": normalized, "page_num": None}] if normalized else []
    return chunks, title
