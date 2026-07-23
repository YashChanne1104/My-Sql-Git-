from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.classifier import classify_sql
from ..services.executor import execute_ddl
from ..core.config import UAT_DB_URL

router = APIRouter(tags=["Approval"])


class ApprovalRequest(BaseModel):
    sql_text: str = Field(..., description="The SQL script the human is approving")
    ai_verdict: str = Field(..., description="'approved' or 'needs_changes', from /review-sql")
    confirmed: bool = Field(
        ...,
        description="Must be explicitly true -- represents the human's manual click. "
                    "This field existing is the entire point of this endpoint: "
                    "the AI verdict alone can NEVER trigger execution."
    )


@router.post("/approve")
def approve_submission(request: ApprovalRequest):
    """
    The manual gate. Regardless of what the AI said, nothing happens here
    unless confirmed=True, which represents an explicit human click --
    never something the AI or this endpoint can set on its own.

    DDL (CREATE/ALTER PROCEDURE, FUNCTION, TRIGGER) -> auto-executed on UAT.
    DML (INSERT/UPDATE/DELETE)                      -> NEVER executed here.
                                                        Only the approved script
                                                        is handed back for the
                                                        human to run themselves.
    """
    if not request.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Approval requires an explicit manual confirmation (confirmed=true)."
        )

    classification = classify_sql(request.sql_text)

    if classification["type"] == "UNKNOWN":
        raise HTTPException(status_code=400, detail=f"Cannot approve: {classification['reason']}")

    if classification["type"] == "DDL":
        result = execute_ddl(UAT_DB_URL, request.sql_text)
        return {
            "sql_type": "DDL",
            "object_type": classification.get("object_type"),
            "action_taken": "auto_executed",
            "execution_result": result,
        }

    # DML -- app NEVER executes this, only returns the approved script
    return {
        "sql_type": "DML",
        "action_taken": "displayed_only",
        "approved_sql": request.sql_text,
        "note": "This DML was approved but NOT executed by the app. "
                "Copy and run it manually against the target environment.",
    }