"""Shared data models. Keep these small and stable — most of the codebase touches them."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(str, Enum):  # str-mixin for sqlite/JSON compatibility, works on 3.10+
    SCRAPED = "scraped"
    FILTERED = "filtered"                              # heuristic deal-breaker
    CANNOT_SCORE_NO_BODY = "cannot_score:no_body"      # < 100 words, refuse to score
    CANNOT_SCORE_NO_PRIMARY_CV = "cannot_score:no_primary_cv"  # missing PRIMARY_* CV
    CANNOT_SCORE_NO_BASE_CV = "cannot_score:no_base_cv"  # legacy alias for old rows
    SCORED = "scored"                                  # has an LLM score
    BELOW_THRESHOLD = "below_threshold"                # scored but not generated
    GENERATED = "generated"                            # CV + cover letter written
    APPLY_QUEUED = "apply_queued"
    APPLY_SUBMITTED = "apply_submitted"
    APPLY_NEEDS_REVIEW = "apply_needs_review"
    APPLY_FAILED = "apply_failed"
    EMPLOYER_RECEIVED = "employer_received"
    WAITING_RESPONSE = "waiting_response"
    REJECTED = "rejected"
    INTERVIEW_INVITED = "interview_invited"


class JobPosting(BaseModel):
    id: str = Field(..., description="Stable hash of source+url")
    source: str
    title: str
    company: str
    location: str | None = None
    url: HttpUrl
    apply_url: HttpUrl | None = None
    posted_at: datetime | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    reason: str


class GeneratedDocs(BaseModel):
    cv_md: str
    cv_html: str
    cover_letter_md: str
    cover_letter_html: str
    output_dir: str
    cv_pdf: str | None = None            # absolute path; None if WeasyPrint unavailable
    cover_letter_pdf: str | None = None  # absolute path; None if WeasyPrint unavailable


class ApplyResult(BaseModel):
    status: JobStatus
    submitted: bool = False
    dry_run: bool = False
    needs_review_reason: str | None = None
    error: str | None = None
    screenshot_path: str | None = None
    confirmation_url: str | None = None
