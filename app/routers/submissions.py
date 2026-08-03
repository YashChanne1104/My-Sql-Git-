from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core import auth
from ..models import models, schemas
from ..services.submission_service import (
    create_submission_record, approve_submission_record, reject_submission_record,
    bulk_approve_submission_records, bulk_reject_submission_records,
)

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("", response_model=schemas.SubmissionOut)
def create_submission(
    payload: schemas.SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
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
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Approval requires confirmed=true")
    return approve_submission_record(db, submission_id, current_user)


@router.post("/{submission_id}/reject", response_model=schemas.SubmissionOut)
def reject_submission(
    submission_id: int,
    payload: schemas.RejectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    return reject_submission_record(db, submission_id, payload.reason, current_user)


@router.post("/bulk-approve", response_model=schemas.BulkActionResult)
def bulk_approve_submissions(
    payload: schemas.BulkApproveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Bulk approval requires confirmed=true")
    result = bulk_approve_submission_records(db, payload.submission_ids, current_user)
    return schemas.BulkActionResult(
        approved=result["approved"], failed=result["failed"], combined_file=result["combined_file"],
    )


@router.post("/bulk-reject", response_model=schemas.BulkActionResult)
def bulk_reject_submissions(
    payload: schemas.BulkRejectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("Approver", "Admin")),
):
    result = bulk_reject_submission_records(db, payload.submission_ids, payload.reason, current_user)
    return schemas.BulkActionResult(rejected=result["rejected"], failed=result["failed"])