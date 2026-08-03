from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core import auth
from ..models import models, schemas

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/summary", response_model=list[schemas.AuditSummaryOut])
def list_audit_summary(
    status: models.SubmissionStatus | None = None,
    sql_type: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Human-readable audit trail: who raised it, what it does (AI-described),
    AI verdict, current status, and who approved/rejected it + when.
    query_summary is generated once at submission time and stored -- this
    endpoint just reads it, no AI calls happen here.
    """
    query = db.query(models.Submission)

    if current_user.role not in (models.RoleEnum.approver, models.RoleEnum.admin):
        query = query.filter(models.Submission.submitted_by_id == current_user.id)

    if status:
        query = query.filter(models.Submission.status == status)
    if sql_type:
        query = query.filter(models.Submission.sql_type == sql_type)

    submissions = (
        query.order_by(models.Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        schemas.AuditSummaryOut(
            id=s.id,
            user=s.submitted_by_email,
            type=s.sql_type,
            query_summary=s.query_summary,
            ai_verdict=s.ai_verdict,
            status=s.status,
            approved_by=s.reviewed_by_email,
            approved_at=s.reviewed_at,
            reject_reason=s.reject_reason,
            raised_at=s.created_at,
            target_database=s.target_database,
        )
        for s in submissions
    ]