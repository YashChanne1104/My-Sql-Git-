from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..core.database import get_db
from ..core import auth
from ..core.config import UAT_DB_URL
from ..models import models, schemas
from ..services.executor import execute_ddl
from ..services.audit import log_action
from ..services.sql_cleaner import swap_database_in_url
from ..services.dml_file_manager import write_approved_file, remove_from_pending_file, write_approved_file_bulk
from ..services.submission_service import create_submission_record

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("", response_model=schemas.SubmissionOut)
def create_submission(
    payload: schemas.SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    All the actual logic (cleaning, classifying, DML syntax validation, AI
    review, saving, file archiving) lives in create_submission_record --
    shared with the /ui/submit browser page so there's exactly one
    implementation, not two that could drift apart.
    """
    return create_submission_record(db, current_user, payload.sql_text)


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
    """
    The manual gate. sql_text, ai_verdict, and target_database are all read
    from the STORED submission -- never from the request body -- so the
    client cannot influence what gets executed, or where, beyond the
    confirmed=true click itself.
    """
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
        exec_url = UAT_DB_URL
        if submission.target_database:
            exec_url = swap_database_in_url(UAT_DB_URL, submission.target_database)

        result = execute_ddl(submission.sql_text, exec_url)
        submission.execution_result = result
    else:
        # DML -- app NEVER executes this, only marks it approved for manual execution
        submission.execution_result = {"status": "not_executed", "reason": "DML requires manual execution"}
        write_approved_file(submission.id, submission.sql_text, current_user.email)
        remove_from_pending_file(submission.id, submission.created_at)

    submission.status = models.SubmissionStatus.approved
    submission.reviewed_by_id = current_user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db,
        action="SUBMISSION_APPROVED",
        actor_id=current_user.id,
        target_type="Submission",
        target_id=submission.id,
        details={
            "sql_type": submission.sql_type,
            "target_database": submission.target_database,
            "execution_result": submission.execution_result,
        },
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
    """Sends the submission back to the developer with a reason."""
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


@router.post("/bulk-approve", response_model=schemas.BulkActionResult)
def bulk_approve_submissions(
    payload: schemas.BulkApproveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Bulk approval requires confirmed=true")

    result = schemas.BulkActionResult()
    dml_batch = []

    for sub_id in payload.submission_ids:
        submission = db.query(models.Submission).filter(models.Submission.id == sub_id).first()

        if not submission:
            result.failed[sub_id] = "Not found"
            continue
        if submission.status != models.SubmissionStatus.pending:
            result.failed[sub_id] = f"Already {submission.status.value}"
            continue
        if submission.ai_verdict == "needs_changes":
            result.failed[sub_id] = "AI verdict is 'needs_changes' -- reject instead"
            continue

        if submission.sql_type == "DDL":
            exec_url = UAT_DB_URL
            if submission.target_database:
                exec_url = swap_database_in_url(UAT_DB_URL, submission.target_database)
            exec_result = execute_ddl(submission.sql_text, exec_url)
            submission.execution_result = exec_result
        else:
            submission.execution_result = {"status": "not_executed", "reason": "DML requires manual execution"}
            dml_batch.append({"id": submission.id, "sql_text": submission.sql_text})

        submission.status = models.SubmissionStatus.approved
        submission.reviewed_by_id = current_user.id
        submission.reviewed_at = datetime.now(timezone.utc)
        result.approved.append(sub_id)

        log_action(
            db, action="SUBMISSION_APPROVED", actor_id=current_user.id,
            target_type="Submission", target_id=submission.id,
            details={"sql_type": submission.sql_type, "bulk": True, "execution_result": submission.execution_result},
        )

    if dml_batch:
        combined_path = write_approved_file_bulk(dml_batch, current_user.email)
        result.combined_file = combined_path
        for item in dml_batch:
            sub = db.query(models.Submission).filter(models.Submission.id == item["id"]).first()
            remove_from_pending_file(item["id"], sub.created_at)

    db.commit()
    return result


@router.post("/bulk-reject", response_model=schemas.BulkActionResult)
def bulk_reject_submissions(
    payload: schemas.BulkRejectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    result = schemas.BulkActionResult()

    for sub_id in payload.submission_ids:
        submission = db.query(models.Submission).filter(models.Submission.id == sub_id).first()
        if not submission:
            result.failed[sub_id] = "Not found"
            continue
        if submission.status != models.SubmissionStatus.pending:
            result.failed[sub_id] = f"Already {submission.status.value}"
            continue

        submission.status = models.SubmissionStatus.rejected
        submission.reject_reason = payload.reason
        submission.reviewed_by_id = current_user.id
        submission.reviewed_at = datetime.now(timezone.utc)
        result.rejected.append(sub_id)

        log_action(
            db, action="SUBMISSION_REJECTED", actor_id=current_user.id,
            target_type="Submission", target_id=submission.id,
            details={"reason": payload.reason, "bulk": True},
        )

    db.commit()
    return result