from app.core.database import SessionLocal, Base, engine
from app.models import models
from app.core import auth

# --- EDIT THESE BEFORE RUNNING ---
ADMIN_EMAIL = "yashchanne64@gmail.com"
ADMIN_PASSWORD = "pass@#123"
# ----------------------------------

Base.metadata.create_all(bind=engine)  # ensure tables exist

db = SessionLocal()

try:
    existing = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()
    if existing:
        print(f"User with email {ADMIN_EMAIL} already exists (role: {existing.role}).")
        if existing.role != models.RoleEnum.admin:
            existing.role = models.RoleEnum.admin
            db.commit()
            print("Updated existing user's role to Admin.")
    else:
        admin_user = models.User(
            email=ADMIN_EMAIL,
            hashed_password=auth.get_password_hash(ADMIN_PASSWORD),
            role=models.RoleEnum.admin,
        )
        db.add(admin_user)
        db.commit()
        print(f"Admin user created: {ADMIN_EMAIL}")
finally:
    db.close()