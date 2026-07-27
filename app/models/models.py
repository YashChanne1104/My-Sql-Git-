import enum
from sqlalchemy import Column, Integer, String, Enum, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class RoleEnum(str, enum.Enum):
    developer = "Developer"
    approver = "Approver"
    admin = "Admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=True, default=None)  # unassigned until admin sets it


# ===========================
# Submission model
# ===========================
class SubmissionStatus(str, enum.Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"

class AuditLog(Base):
    __tablename__ = "audit_logs"
 
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
 
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null for system/pre-login events
    action = Column(String, nullable=False, index=True)                # e.g. "SUBMISSION_APPROVED"
    target_type = Column(String, nullable=True, index=True)             # e.g. "Submission", "User"
    target_id = Column(Integer, nullable=True, index=True)
 
    details = Column(JSON, nullable=True)   # free-form extra context, e.g. {"role": "Approver"}
 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
 
    actor = relationship("User", foreign_keys=[actor_id])


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    sql_text = Column(Text, nullable=False)
    sql_type = Column(String, nullable=False)          # DDL / DML
    object_type = Column(String, nullable=True)         # PROCEDURE / FUNCTION / TRIGGER

    # AI review results, captured at submission time -- never re-trusted from the client later
    ai_verdict = Column(String, nullable=False)          # approved / needs_changes
    ai_summary = Column(Text, nullable=True)
    ai_review_json = Column(JSON, nullable=True)         # full SQLReviewReport, for audit detail

    status = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.pending)

    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    reject_reason = Column(Text, nullable=True)
    execution_result = Column(JSON, nullable=True)       # what execute_ddl() returned, if DDL

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    submitted_by = relationship("User", foreign_keys=[submitted_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    
    target_database = Column(String, nullable=True)  # e.g. "ETransReporting", from USE statement