"""POST /ingest endpoint — accepts multipart or JSON, enqueues background pipeline."""
from __future__ import annotations

import base64
import ipaddress
import re
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import insert

from app.core.database import AsyncSessionLocal
from app.models.models import Source
from app.pipeline.pipeline import run_pipeline
from app.schemas.ingest import IngestResponse

router = APIRouter()

# Maximum upload size: 50 MB (PIPE-01 / threat model)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Private/loopback IP patterns for SSRF protection
_PRIVATE_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Return True if URL is safe to fetch (not a private/loopback address).

    Blocks:
    - Non-http/https schemes (ftp, file, etc.)
    - Private IP ranges: 127.x, 10.x, 172.16.x, 192.168.x, 169.254.x
    - IPv6 loopback (::1) and ULA (fc00::/7)
    - DNS resolution failures (fail-closed)
    """
    import socket
    # Only allow http/https
    if not re.match(r"^https?://", url, re.IGNORECASE):
        return False
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname
        if not hostname:
            return False
        # Resolve hostname to IP
        addrs = socket.getaddrinfo(hostname, None)
        for addr in addrs:
            ip = ipaddress.ip_address(addr[4][0])
            for net in _PRIVATE_NETS:
                if ip in net:
                    return False
        return True
    except Exception:
        return False  # Resolve failure → block (fail-closed)


@router.post("", response_model=IngestResponse, status_code=202)
async def ingest(
    request: Request,
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    """Accept file, URL, or text and enqueue the background pipeline.

    Supports two content types:
    - multipart/form-data: fields course_id (int), kind (str), file (UploadFile)
    - application/json: {course_id, kind, url} OR {course_id, kind, title, text}

    Returns {source_id, status: "pending"} immediately (PIPE-01).
    """
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        return await _handle_multipart(request, background_tasks, force)
    elif "application/json" in content_type:
        return await _handle_json(request, background_tasks, force)
    else:
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be multipart/form-data or application/json",
        )


async def _handle_multipart(request: Request, background_tasks: BackgroundTasks, force: bool):
    form = await request.form()
    course_id_raw = form.get("course_id", "")
    kind = str(form.get("kind", ""))
    upload: UploadFile | None = form.get("file")

    try:
        course_id = int(course_id_raw)
    except (ValueError, TypeError):
        raise HTTPException(400, "course_id must be an integer")

    if not course_id or not kind or not upload:
        raise HTTPException(400, "course_id, kind, and file are required")
    if kind not in ("pdf", "image"):
        raise HTTPException(400, f"Unsupported kind for file upload: {kind}")

    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds 50MB limit")

    filename = upload.filename or f"upload.{kind}"
    raw_text_b64 = base64.b64encode(data).decode()  # Store bytes as base64 in Text column

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            insert(Source).values(
                course_id=course_id,
                source_type=kind,
                title=filename,
                raw_text=raw_text_b64,
                status="pending",
            ).returning(Source.id)
        )
        source_id = result.scalar_one()
        await session.commit()

    background_tasks.add_task(run_pipeline, source_id, force)
    return IngestResponse(source_id=source_id, status="pending")


async def _handle_json(request: Request, background_tasks: BackgroundTasks, force: bool):
    body = await request.json()
    course_id = body.get("course_id")
    kind = body.get("kind")

    if not course_id or not kind:
        raise HTTPException(400, "course_id and kind are required")

    if kind == "url":
        url = body.get("url")
        if not url:
            raise HTTPException(400, "url is required for kind=url")
        if not _is_safe_url(url):
            raise HTTPException(
                400,
                "URL is not allowed (private/loopback address or non-HTTP scheme)",
            )

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                insert(Source).values(
                    course_id=course_id,
                    source_type="url",
                    source_uri=url,
                    status="pending",
                ).returning(Source.id)
            )
            source_id = result.scalar_one()
            await session.commit()

    elif kind == "text":
        text = body.get("text", "")
        title = body.get("title")
        if not text:
            raise HTTPException(400, "text is required for kind=text")

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                insert(Source).values(
                    course_id=course_id,
                    source_type="text",
                    title=title,
                    raw_text=text,
                    status="pending",
                ).returning(Source.id)
            )
            source_id = result.scalar_one()
            await session.commit()
    else:
        raise HTTPException(400, f"Unsupported kind: {kind}")

    background_tasks.add_task(run_pipeline, source_id, force)
    return IngestResponse(source_id=source_id, status="pending")
