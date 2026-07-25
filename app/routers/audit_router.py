from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core import auth
from ..models import models, schemas

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=list[schemas.AuditLogOut])
def list_audit_logs(
    action: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(5, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Approver/Admin: full system audit trail, paginated 5 at a time by default.
    Developer: same pagination, but auto-filtered to entries where THEY are the
    actor -- their own submissions, their own signup event, etc. This filter is
    applied automatically from their token, never something they pass in.
    """
    query = db.query(models.AuditLog)

    if current_user.role not in (models.RoleEnum.approver, models.RoleEnum.admin):
        query = query.filter(models.AuditLog.actor_id == current_user.id)

    if action:
        query = query.filter(models.AuditLog.action == action)
    if target_type:
        query = query.filter(models.AuditLog.target_type == target_type)
    if target_id:
        query = query.filter(models.AuditLog.target_id == target_id)

    return (
        query.order_by(models.AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )