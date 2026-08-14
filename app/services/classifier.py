# pyrefly: ignore [missing-import]
import sqlparse
# pyrefly: ignore [missing-import]
from sqlparse.sql import Statement, Comment
from enum import Enum

from .sql_cleaner import strip_for_classification


class SQLType(str, Enum):
    DDL = "DDL"
    DML = "DML"
    UNKNOWN = "UNKNOWN"


DDL_KEYWORDS = {"CREATE", "ALTER", "DROP"}
DML_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "MERGE"}
DDL_OBJECT_TYPES = {"PROCEDURE", "PROC", "FUNCTION", "TRIGGER"}


def classify_sql(sql_text: str) -> dict:
    """
    Classifies a SQL script as DDL or DML based on its first meaningful statement.

    sql_text is regex-stripped of comments/USE/GO/SET boilerplate via
    strip_for_classification() first, so callers can pass either raw or
    cleaned SQL and still get a correct classification. The sqlparse-level
    comment filtering below is kept as a second layer of defense, not the
    primary mechanism.
    """
    sql_text = strip_for_classification(sql_text).strip()
    if not sql_text:
        return {"type": SQLType.UNKNOWN, "keyword": None, "object_type": None, "reason": "Empty input"}

    parsed = sqlparse.parse(sql_text)
    if not parsed:
        return {"type": SQLType.UNKNOWN, "keyword": None, "object_type": None, "reason": "Could not parse SQL"}

    statement: Statement = parsed[0]

    tokens = [
        t for t in statement.tokens
        if not t.is_whitespace
        and not isinstance(t, Comment)
        and t.ttype not in (sqlparse.tokens.Comment.Single, sqlparse.tokens.Comment.Multiline)
    ]

    if not tokens:
        return {"type": SQLType.UNKNOWN, "keyword": None, "object_type": None, "reason": "No tokens found"}

    first_keyword = tokens[0].normalized.upper()

    if first_keyword in DDL_KEYWORDS:
        object_type = None
        if len(tokens) > 1:
            candidate = tokens[1].normalized.upper()
            if candidate == "OR" and len(tokens) > 3:
                candidate = tokens[3].normalized.upper()
            object_type = candidate

        return {
            "type": SQLType.DDL,
            "keyword": first_keyword,
            "object_type": object_type,
            "reason": f"Starts with {first_keyword}, targets {object_type or 'unknown object type'}"
        }

    if first_keyword in DML_KEYWORDS:
        return {
            "type": SQLType.DML,
            "keyword": first_keyword,
            "object_type": None,
            "reason": f"Starts with {first_keyword} -- data modification"
        }

    return {
        "type": SQLType.UNKNOWN,
        "keyword": first_keyword,
        "object_type": None,
        "reason": f"'{first_keyword}' is not a recognized DDL or DML starting keyword"
    }