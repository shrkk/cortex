from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str               # "course-{id}" | "concept-{id}" | "flashcard-{id}" | "quiz-{id}"
    type: str             # "course" | "concept" | "flashcard" | "quiz"
    data: dict[str, Any]  # type-specific payload; NEVER include embedding vectors


class GraphEdge(BaseModel):
    id: str
    source: str           # prefixed node id string
    target: str           # prefixed node id string
    type: str             # "contains" | "co_occurrence" | "prerequisite" | "related"
    data: dict[str, Any] = {}


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    # No from_attributes — assembled from dicts in _build_graph_payload(), not ORM objects
