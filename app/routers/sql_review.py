from typing import Literal, Optional
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_mistralai import ChatMistralAI
from pydantic import BaseModel, Field
from ..services.classifier import classify_sql

# Load environment variables
load_dotenv()

router = APIRouter(tags=["SQL Review"])

# Initialize Mistral model
model = ChatMistralAI(
    model="mistral-large-latest",
    temperature=0
)


# ===========================
# Request Model
# ===========================
class SQLRequest(BaseModel):
    sql_text: str = Field(..., description="SQL script to analyze")


# ===========================
# Response Models
# ===========================
class SQLReviewReport(BaseModel):
    sql_type: str = Field(description="DDL or DML, as detected by the classifier")
    object_type: Optional[str] = Field(
        default=None, description="PROCEDURE, FUNCTION, TRIGGER, TABLE, etc. (DDL only)"
    )
    verdict: Literal["approved", "needs_changes"] = Field(
        description="'approved' only if there are no safety concerns and no high severity issues"
    )
    syntax_risk: Literal["low", "medium", "high"] = Field(
        description="Risk of syntax errors or runtime failure"
    )
    safety_concerns: list[str] = Field(
        default_factory=list,
        description="e.g. DELETE/UPDATE without WHERE, DROP without IF EXISTS, no transaction handling"
    )
    performance_issues: list[str] = Field(
        default_factory=list,
        description="e.g. cursors instead of set-based logic, SELECT *, non-sargable predicates"
    )
    naming_convention_issues: list[str] = Field(
        default_factory=list,
        description="e.g. missing schema prefix, inconsistent casing, unclear names"
    )
    summary: str = Field(description="2-3 sentence plain-English summary for the human approver")
    suggested_sql: Optional[str] = Field(
        default=None, description="Corrected/improved SQL, only if real issues were found"
    )


# Structured Output
structured_model = model.with_structured_output(SQLReviewReport)


# ===========================
# Core review logic (reusable, not tied to the HTTP layer)
# ===========================
def run_sql_review(sql_text: str) -> SQLReviewReport:
    classification = classify_sql(sql_text)

    if classification["type"] == "UNKNOWN":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot review: {classification['reason']}"
        )

    prompt = ChatPromptTemplate.from_template(
        """
        You are a Senior SQL Server DBA performing a pre-deployment review.

        SQL Type: {sql_type} ({object_type})

        Review it strictly for:
        1. SAFETY -- the most important check. Flag any DELETE/UPDATE without a WHERE
           clause, any DROP without IF EXISTS, and any operation missing transaction
           handling where it matters. A safety concern should almost always mean
           verdict = "needs_changes".
        2. PERFORMANCE -- cursors that could be set-based, SELECT *, missing WHERE/JOIN
           index consideration, non-sargable predicates.
        3. NAMING CONVENTIONS -- schema prefixes (dbo.), consistent casing, clear names.
        4. Provide a corrected/improved version in suggested_sql ONLY if you found real
           issues. If the script is already clean, leave suggested_sql null.

        Be direct and specific -- reference actual column/table names from the script,
        not generic advice. Return ONLY the structured response.

        SQL Script:
        {sql_text}
        """
    )

    messages = prompt.format_messages(
        sql_text=sql_text,
        sql_type=classification["type"],
        object_type=classification.get("object_type") or "N/A",
    )

    report: SQLReviewReport = structured_model.invoke(messages)
    report.sql_type = classification["type"]
    report.object_type = classification.get("object_type")
    return report


# ===========================
# API Endpoint
# ===========================
@router.post(
    "/review-sql",
    response_model=SQLReviewReport,
    summary="Classify and Review a SQL Script"
)
def review_sql_endpoint(request: SQLRequest):
    return run_sql_review(request.sql_text)