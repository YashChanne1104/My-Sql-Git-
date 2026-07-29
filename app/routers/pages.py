from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core import auth
from ..models import models

router = APIRouter(prefix="/ui", tags=["Frontend"])
templates = Jinja2Templates(directory="app/templates")
response = RedirectResponse(url="/ui/login", status_code=303)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, current_user: models.User | None = Depends(auth.get_current_user_optional)):
    return templates.TemplateResponse("login.html", {"request": request, "current_user": current_user})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = auth.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "current_user": None, "error": "Incorrect email or password", "email": email},
            status_code=401,
        )

    access_token = auth.create_access_token(
        data={"sub": user.email, "role": user.role.value if user.role else None}
    )

    response = RedirectResponse(url="/ui/login", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,       # JavaScript can't read this -- mitigates XSS token theft
        samesite="lax",      # sent on normal navigation, blocked on cross-site POSTs -- CSRF mitigation
        max_age=60 * 60,      # matches ACCESS_TOKEN_EXPIRE_MINUTES default; adjust if you change that
        # secure=True,        # UNCOMMENT once served over HTTPS -- required for cookie to be sent then
    )
    return response


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, current_user: models.User | None = Depends(auth.get_current_user_optional)):
    return templates.TemplateResponse("signup.html", {"request": request, "current_user": current_user})


@router.post("/signup", response_class=HTMLResponse)
def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if auth.get_user_by_email(db, email):
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "current_user": None, "error": "Email already registered", "email": email},
            status_code=400,
        )

    new_user = models.User(
        email=email,
        hashed_password=auth.get_password_hash(password),
        role=None,
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/ui/login", status_code=303)


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/ui/login", status_code=303)
    response.delete_cookie("access_token")
    return response