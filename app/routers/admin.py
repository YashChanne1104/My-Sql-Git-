from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core import auth
from ..models import models, schemas

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.require_role("Admin")),
):
    """List every user with their current role — the role master table."""
    return db.query(models.User).order_by(models.User.id).all()


@router.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.require_role("Admin")),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}/role", response_model=schemas.UserOut)
def update_user_role(
    user_id: int,
    payload: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.require_role("Admin")),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin_user.id and payload.role != models.RoleEnum.admin:
        # prevent an admin from accidentally demoting themselves
        remaining_admins = (
            db.query(models.User)
            .filter(models.User.role == models.RoleEnum.admin, models.User.id != user.id)
            .count()
        )
        if remaining_admins == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last remaining Admin",
            )

    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.require_role("Admin")),
):
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"detail": f"User {user.email} deleted"}