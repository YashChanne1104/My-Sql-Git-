
from sqlalchemy.orm import Session
from app.models import models


def log_action(
    db: Session,
    action: str,
    actor_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    details: dict | None = None,
) -> None:
    """
    Writes one audit log entry. Call this alongside db.commit() for anything
    that matters later: who did what, to what, and when.

    Does NOT commit on its own -- caller should already be committing the
    main change (e.g. the submission update) in the same request. This gets
    added to that same session so it lands in the same transaction.
    """
    entry = models.AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(entry)