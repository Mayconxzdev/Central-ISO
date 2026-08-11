from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# Este piloto público não implementa autenticação corporativa.

# === Document/Note ===

class NoteCreate(BaseModel):
    author: str | None = None
    note: str = Field(min_length=2, max_length=5000)


class AssistantQuery(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class StatusUpdate(BaseModel):
    status: str
    justification: str = Field(min_length=3, max_length=2000)


class PendingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    area: str
    severity: str
    status: str
    description: str
    risk: str
    responsible_role: str
    due_date: date | None
    source_path: str
    source_excerpt: str
    created_at: datetime
    updated_at: datetime
    resolved: bool