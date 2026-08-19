import enum
from sqlalchemy import Column, Integer, String, Enum, Text, DateTime, JSON
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.sql import func

from ..core.database import Base


class RoleEnum(str, enum.Enum):
    developer = "Developer"
    approver = "Approver"
    admin = "Admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=True, default=None)


class SubmissionStatus(str, enum.Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_id = Column(Integer, nullable=True)  # FK removed
    action = Column(String(255), nullable=False, index=True)
    target_type = Column(String(100), nullable=True, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    actor = relationship(
        "User",
        primaryjoin="foreign(AuditLog.actor_id) == User.id",
        viewonly=True,
    )


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sql_text = Column(Text, nullable=False)
    sql_type = Column(String(50), nullable=False)
    object_type = Column(String(100), nullable=True)

    ai_verdict = Column(String(50), nullable=False)
    ai_summary = Column(Text, nullable=True)
    ai_review_json = Column(JSON, nullable=True)

    status = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.pending)

    submitted_by_id = Column(Integer, nullable=False)  # FK removed
    reviewed_by_id = Column(Integer, nullable=True)    # FK removed

    reject_reason = Column(Text, nullable=True)
    execution_result = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    target_database = Column(String(255), nullable=True)
    query_summary = Column(Text, nullable=True)

    submitted_by = relationship(
        "User",
        primaryjoin="foreign(Submission.submitted_by_id) == User.id",
        viewonly=True,
    )
    reviewed_by = relationship(
        "User",
        primaryjoin="foreign(Submission.reviewed_by_id) == User.id",
        viewonly=True,
    )

    optional_suggestions = Column(JSON, nullable=True)
    suggested_sql = Column(Text, nullable=True)

    @property
    def submitted_by_email(self) -> str | None:
        return self.submitted_by.email if self.submitted_by else None

    @property
    def reviewed_by_email(self) -> str | None:
        return self.reviewed_by.email if self.reviewed_by else None

    @property
    def summary_text(self) -> str:
        raised = f"{self.sql_type} submitted by {self.submitted_by_email or 'unknown'} on {self.created_at.strftime('%d %b, %H:%M')}"
        if self.status.value == "Pending":
            return f"{raised} — awaiting review."
        reviewer = self.reviewed_by_email or "unknown"
        when = self.reviewed_at.strftime('%d %b, %H:%M') if self.reviewed_at else "unknown time"
        if self.status.value == "Approved":
            return f"{raised} — approved by {reviewer} on {when}."
        if self.status.value == "Rejected":
            reason = f': "{self.reject_reason}"' if self.reject_reason else "."
            return f"{raised} — rejected by {reviewer} on {when}{reason}"
        return raised