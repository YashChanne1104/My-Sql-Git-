from datetime import datetime
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, Field

from .models import RoleEnum, SubmissionStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: RoleEnum | None = None

    class Config:
        from_attributes = True


class RoleAssign(BaseModel):
    email: EmailStr
    role: RoleEnum


class RoleUpdate(BaseModel):
    role: RoleEnum


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: str | None = None
    role: str | None = None


# ===========================
# Submission schemas
# ===========================
class SubmissionCreate(BaseModel):
    sql_text: str


class SubmissionOut(BaseModel):
    id: int
    sql_text: str
    sql_type: str
    object_type: str | None
    ai_verdict: str
    ai_summary: str | None
    status: SubmissionStatus
    submitted_by_id: int
    reviewed_by_id: int | None
    reject_reason: str | None
    execution_result: dict | None
    created_at: datetime
    reviewed_at: datetime | None
    target_database: str | None  # <-- NEW
    optional_suggestions: list[str] = []
    suggested_sql: str | None = None
    

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    confirmed: bool = Field(
        ...,
        description="Must be explicitly true -- represents the human's manual click."
    )


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Why this submission is being sent back")

class AuditSummaryOut(BaseModel):
    id: int

    user: str | None           # who raised it
    type: str                  # DDL or DML
    query_summary: str | None  # what the SQL actually does (AI-generated)

    ai_verdict: str            # approved / needs_changes

    status: SubmissionStatus   # Pending / Approved / Rejected
    approved_by: str | None    # who reviewed it (approved OR rejected)
    approved_at: datetime | None
    reject_reason: str | None

    raised_at: datetime
    target_database: str | None

    class Config:
        from_attributes = True

class BulkRejectRequest(BaseModel):
    submission_ids: list[int] = Field(..., min_items=1, description="List of submission IDs to reject")
    reason: str = Field(..., min_length=1, description="Reason for rejection")

class BulkActionResult(BaseModel):
    approved: list[int] = Field(default_factory=list)
    rejected: list[int] = Field(default_factory=list)
    failed: dict[int, str] = Field(default_factory=dict)
    combined_file: str | None = None

class BulkApproveRequest(BaseModel):
    submission_ids: list[int] = Field(..., min_items=1, description="List of submission IDs to approve")
    confirmed: bool = Field(..., description="Must be explicitly true")