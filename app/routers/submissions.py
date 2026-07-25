from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..core.database import get_db
from ..core import auth
from ..core.config import UAT_DB_URL
from ..models import models, schemas
from ..services.classifier import classify_sql
from ..services.executor import execute_ddl
from ..services.audit import log_action
from ..routers.sql_review import run_sql_review

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("", response_model=schemas.SubmissionOut)
def create_submission(
    payload: schemas.SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    classification = classify_sql(payload.sql_text)
    if classification["type"] == "UNKNOWN":
        raise HTTPException(status_code=400, detail=f"Cannot submit: {classification['reason']}")

    review = run_sql_review(payload.sql_text)

    submission = models.Submission(
        sql_text=payload.sql_text,
        sql_type=classification["type"],
        object_type=classification.get("object_type"),
        ai_verdict=review.verdict,
        ai_summary=review.summary,
        ai_review_json=review.model_dump(),
        status=models.SubmissionStatus.pending,
        submitted_by_id=current_user.id,
    )
    db.add(submission)
    db.flush()  # get submission.id before commit, for the audit log

    log_action(
        db,
        action="SUBMISSION_CREATED",
        actor_id=current_user.id,
        target_type="Submission",
        target_id=submission.id,
        details={"sql_type": submission.sql_type, "ai_verdict": submission.ai_verdict},
    )

    db.commit()
    db.refresh(submission)
    return submission


@router.get("", response_model=list[schemas.SubmissionOut])
def list_submissions(
    status: models.SubmissionStatus | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.Submission)

    if current_user.role not in (models.RoleEnum.approver, models.RoleEnum.admin):
        query = query.filter(models.Submission.submitted_by_id == current_user.id)

    if status:
        query = query.filter(models.Submission.status == status)

    return query.order_by(models.Submission.created_at.desc()).all()


@router.get("/{submission_id}", response_model=schemas.SubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_owner = submission.submitted_by_id == current_user.id
    is_reviewer = current_user.role in (models.RoleEnum.approver, models.RoleEnum.admin)
    if not (is_owner or is_reviewer):
        raise HTTPException(status_code=403, detail="Not your submission")

    return submission


@router.post("/{submission_id}/approve", response_model=schemas.SubmissionOut)
def approve_submission(
    submission_id: int,
    payload: schemas.ApproveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Approval requires confirmed=true")

    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != models.SubmissionStatus.pending:
        raise HTTPException(status_code=400, detail=f"Submission already {submission.status.value}")

    if submission.ai_verdict == "needs_changes":
        raise HTTPException(
            status_code=400,
            detail="Cannot approve: AI review flagged this as 'needs_changes'. "
                    "Reject it and ask the developer to resubmit a fixed version instead."
        )

    if submission.sql_type == "DDL":
        result = execute_ddl(submission.sql_text, UAT_DB_URL)
        submission.execution_result = result
    else:
        submission.execution_result = {"status": "not_executed", "reason": "DML requires manual execution"}

    submission.status = models.SubmissionStatus.approved
    submission.reviewed_by_id = current_user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db,
        action="SUBMISSION_APPROVED",
        actor_id=current_user.id,
        target_type="Submission",
        target_id=submission.id,
        details={"sql_type": submission.sql_type, "execution_result": submission.execution_result},
    )

    db.commit()
    db.refresh(submission)
    return submission


@router.post("/{submission_id}/reject", response_model=schemas.SubmissionOut)
def reject_submission(
    submission_id: int,
    payload: schemas.RejectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != models.SubmissionStatus.pending:
        raise HTTPException(status_code=400, detail=f"Submission already {submission.status.value}")

    submission.status = models.SubmissionStatus.rejected
    submission.reject_reason = payload.reason
    submission.reviewed_by_id = current_user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db,
        action="SUBMISSION_REJECTED",
        actor_id=current_user.id,
        target_type="Submission",
        target_id=submission.id,
        details={"reason": payload.reason},
    )

    db.commit()
    db.refresh(submission)
    return submission