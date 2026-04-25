from pydantic import BaseModel
from typing import Literal


class IngestFileForm(BaseModel):
    """Used as form field extraction guide — actual parsing uses UploadFile + Form."""
    course_id: int
    kind: Literal["pdf", "image", "text", "url"]


class IngestURLBody(BaseModel):
    """JSON body for URL ingest."""
    course_id: int
    kind: Literal["url"]
    url: str


class IngestTextBody(BaseModel):
    """JSON body for text ingest."""
    course_id: int
    kind: Literal["text"]
    title: str | None = None
    text: str


class IngestResponse(BaseModel):
    source_id: int
    status: str = "pending"
