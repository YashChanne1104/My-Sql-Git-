from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models import models
from ..services.classifier import classify_sql
from ..services.sql_cleaner import extract_target_database, clean_sql_script
from ..services.dml_validator import validate_dml_syntax
from ..services.dml_file_manager import append_to_pending_file
from ..services.audit import log_action
from ..routers.sql_review import run_sql_review


def create_submission_record(db: Session, current_user: models.User, raw_sql_text: str) -> models.Submission:
    """
    The single source of truth for turning raw pasted SQL into a saved,
    reviewed Submission record. Used by BOTH the /submissions API endpoint
    and the /ui/submit browser page, so there's exactly one place this
    logic lives -- no duplication, no drift between the two entry points.

    Raises HTTPException on invalid input (same as the API always has).
    """
    target_db = extract_target_database(raw_sql_text)
    cleaned_sql = clean_sql_script(raw_sql_text)

    classification = classify_sql(cleaned_sql)
    if classification["type"] == "UNKNOWN":
        raise HTTPException(status_code=400, detail=f"Cannot submit: {classification['reason']}")

    if classification["type"] == "DML":
        syntax_check = validate_dml_syntax(cleaned_sql, classification["keyword"])
        if not syntax_check["valid"]:
            raise HTTPException(status_code=400, detail=f"Invalid DML syntax: {syntax_check['reason']}")

    review = run_sql_review(cleaned_sql)

    submission = models.Submission(
        sql_text=cleaned_sql,
        sql_type=classification["type"],
        object_type=classification.get("object_type"),
        target_database=target_db,
        ai_verdict=review.verdict,
        ai_summary=review.summary,
        ai_review_json=review.model_dump(),
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