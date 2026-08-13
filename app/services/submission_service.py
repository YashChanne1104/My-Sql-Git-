from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from fastapi import HTTPException

from ..models import models
from ..services.classifier import classify_sql
from ..services.sql_cleaner import extract_target_database, clean_sql_script, swap_database_in_url
from ..services.dml_validator import validate_dml_syntax
from ..services.dml_file_manager import (
    append_to_pending_file, remove_from_pending_file,
    write_approved_file, write_approved_file_bulk,
)
from ..services.executor import execute_ddl
from ..services.audit import log_action
from ..services.audit_summarizer import generate_query_summary
from ..routers.sql_review import run_sql_review
from ..core.config import UAT_DB_URL


def create_submission_record(db: Session, current_user: models.User, raw_sql_text: str) -> models.Submission:
    target_db = extract_target_database(raw_sql_text)
    cleaned_sql = clean_sql_script(raw_sql_text)

    # Classify on the cleaned SQL (used for storage/execution/validation below)
    classification = classify_sql(cleaned_sql)
    if classification["type"] == "UNKNOWN":
        raise HTTPException(status_code=400, detail=f"Cannot submit: {classification['reason']}")

    if classification["type"] == "DML":
        syntax_check = validate_dml_syntax(cleaned_sql, classification["keyword"])
        if not syntax_check["valid"]:
            raise HTTPException(status_code=400, detail=f"Invalid DML syntax: {syntax_check['reason']}")

    # Review the RAW sql_text -- matches what /review-sql shows the user,
    # since that endpoint reviews raw_sql_text with no cleaning applied.
    review = run_sql_review(raw_sql_text)
    query_summary = generate_query_summary(cleaned_sql, classification["type"])

    submission = models.Submission(
        sql_text=cleaned_sql,
        sql_type=classification["type"],
        object_type=classification.get("object_type"),
        target_database=target_db,
        query_summary=query_summary,
        ai_verdict=review.verdict,
        ai_summary=review.summary,
        ai_review_json=review.model_dump(),
        optional_suggestions=review.optional_suggestions,
        suggested_sql=review.suggested_sql,
        status=models.SubmissionStatus.pending,
        submitted_by_id=current_user.id,
    )
    db.add(submission)
    db.flush()

    log_action(
        db, action="SUBMISSION_CREATED", actor_id=current_user.id,
        target_type="Submission", target_id=submission.id,
        details={"sql_type": submission.sql_type, "ai_verdict": submission.ai_verdict, "target_database": target_db},
    )

    db.commit()
    db.refresh(submission)

    if submission.sql_type == "DML":
        append_to_pending_file(submission.id, submission.sql_text, current_user.email)

    return submission


def approve_submission_record(db: Session, submission_id: int, current_user: models.User) -> models.Submission:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != models.SubmissionStatus.pending:
        raise HTTPException(status_code=400, detail=f"Submission already {submission.status.value}")
    if submission.ai_verdict == "needs_changes":
        raise HTTPException(
            status_code=400,
            detail="Cannot approve: AI review flagged this as 'needs_changes'. Reject and ask for a resubmit."
        )

    if submission.sql_type == "DDL":
        exec_url = UAT_DB_URL
        if submission.target_database:
            exec_url = swap_database_in_url(UAT_DB_URL, submission.target_database)
        submission.execution_result = execute_ddl(submission.sql_text, exec_url)
    else:
        submission.execution_result = {"status": "not_executed", "reason": "DML requires manual execution"}
        write_approved_file(submission.id, submission.sql_text, current_user.email)
        remove_from_pending_file(submission.id, submission.created_at)

    submission.status = models.SubmissionStatus.approved
    submission.reviewed_by_id = current_user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db, action="SUBMISSION_APPROVED", actor_id=current_user.id,
        target_type="Submission", target_id=submission.id,
        details={"sql_type": submission.sql_type, "target_database": submission.target_database,
                  "execution_result": submission.execution_result},
    )

    db.commit()
    db.refresh(submission)
    return submission


def reject_submission_record(db: Session, submission_id: int, reason: str, current_user: models.User) -> models.Submission:
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != models.SubmissionStatus.pending:
        raise HTTPException(status_code=400, detail=f"Submission already {submission.status.value}")

    submission.status = models.SubmissionStatus.rejected
    submission.reject_reason = reason
    submission.reviewed_by_id = current_user.id
    submission.reviewed_at = datetime.now(timezone.utc)

    log_action(
        db, action="SUBMISSION_REJECTED", actor_id=current_user.id,
        target_type="Submission", target_id=submission.id, details={"reason": reason},
    )

    db.commit()
    db.refresh(submission)
    return submission


def bulk_approve_submission_records(db: Session, submission_ids: list[int], current_user: models.User) -> dict:
    approved, failed = [], {}
    dml_batch = []

    for sub_id in submission_ids:
        submission = db.query(models.Submission).filter(models.Submission.id == sub_id).first()

        if not submission:
            failed[sub_id] = "Not found"
            continue
        if submission.status != models.SubmissionStatus.pending:
            failed[sub_id] = f"Already {submission.status.value}"
            continue
        if submission.ai_verdict == "needs_changes":
            failed[sub_id] = "AI verdict is 'needs_changes' -- reject instead"
            continue

        if submission.sql_type == "DDL":
            exec_url = UAT_DB_URL
            if submission.target_database:
                exec_url = swap_database_in_url(UAT_DB_URL, submission.target_database)
            submission.execution_result = execute_ddl(submission.sql_text, exec_url)
        else:
            submission.execution_result = {"status": "not_executed", "reason": "DML requires manual execution"}
            dml_batch.append({"id": submission.id, "sql_text": submission.sql_text})

        submission.status = models.SubmissionStatus.approved
        submission.reviewed_by_id = current_user.id
        submission.reviewed_at = datetime.now(timezone.utc)
        approved.append(sub_id)

        log_action(
            db, action="SUBMISSION_APPROVED", actor_id=current_user.id,
            target_type="Submission", target_id=submission.id,
            details={"sql_type": submission.sql_type, "bulk": True, "execution_result": submission.execution_result},
        )

    combined_file = None
    if dml_batch:
        combined_file = write_approved_file_bulk(dml_batch, current_user.email)
        for item in dml_batch:
            sub = db.query(models.Submission).filter(models.Submission.id == item["id"]).first()
            remove_from_pending_file(item["id"], sub.created_at)

    db.commit()
    return {"approved": approved, "failed": failed, "combined_file": combined_file}


def bulk_reject_submission_records(db: Session, submission_ids: list[int], reason: str, current_user: models.User) -> dict:
    rejected, failed = [], {}

    for sub_id in submission_ids:
        submission = db.query(models.Submission).filter(models.Submission.id == sub_id).first()
        if not submission:
            failed[sub_id] = "Not found"
            continue
        if submission.status != models.SubmissionStatus.pending:
            failed[sub_id] = f"Already {submission.status.value}"
            continue

        submission.status = models.SubmissionStatus.rejected
        submission.reject_reason = reason
        submission.reviewed_by_id = current_user.id
        submission.reviewed_at = datetime.now(timezone.utc)
        rejected.append(sub_id)

        log_action(
            db, action="SUBMISSION_REJECTED", actor_id=current_user.id,
            target_type="Submission", target_id=submission.id,
            details={"reason": reason, "bulk": True},
        )

    db.commit()
    return {"rejected": rejected, "failed": failed}