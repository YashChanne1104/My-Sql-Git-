from datetime import datetime
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

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    confirmed: bool = Field(
        ...,
        description="Must be explicitly true -- represents the human's manual click."
    )


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Why this submission is being sent back")