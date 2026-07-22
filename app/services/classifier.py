# pyrefly: ignore [missing-import]
import sqlparse
# pyrefly: ignore [missing-import]
from sqlparse.sql import Statement
from enum import Enum


class SQLType(str, Enum):
    DDL = "DDL"
    DML = "DML"
    UNKNOWN = "UNKNOWN"


# Keywords that identify each category, checked against the first real token
DDL_KEYWORDS = {"CREATE", "ALTER", "DROP"}
DML_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "MERGE"}

# CREATE can be followed by different object types -- we care about these for your use case
DDL_OBJECT_TYPES = {"PROCEDURE", "PROC", "FUNCTION", "TRIGGER"}


def classify_sql(sql_text: str) -> dict:
    """
    Classifies a SQL script as DDL or DML based on its first meaningful statement.
    Returns a dict with the classification, matched keyword, and object type (if DDL).

    Why check only the FIRST statement's first keyword:
    In this workflow, a submission is expected to be one coherent change
    (one SP, one function, one trigger, or one DML block) -- not a mixed batch.
    If you later allow multi-statement submissions, this should loop over
    sqlparse.parse() results instead of just the first one.
    """
    sql_text = sql_text.strip()
    if not sql_text:
        return {"type": SQLType.UNKNOWN, "keyword": None, "object_type": None, "reason": "Empty input"}

    parsed = sqlparse.parse(sql_text)
    if not parsed:
        return {"type": SQLType.UNKNOWN, "keyword": None, "object_type": None, "reason": "Could not parse SQL"}

    statement: Statement = parsed[0]

    # Pull out real tokens, skipping whitespace/comments
    tokens = [t for t in statement.tokens if not t.is_whitespace and t.ttype not in (sqlparse.tokens.Comment.Single, sqlparse.tokens.Comment.Multiline)]

    if not tokens:
        return {"type": SQLType.UNKNOWN, "keyword": None, "object_type": None, "reason": "No tokens found"}

    first_keyword = tokens[0].normalized.upper()

    if first_keyword in DDL_KEYWORDS:
        # Look at the next token to find object type (PROCEDURE, FUNCTION, TRIGGER, TABLE, etc.)
        object_type = None
        if len(tokens) > 1:
            candidate = tokens[1].normalized.upper()
            # Handle "CREATE OR ALTER" -- object type is actually token[3] in that case
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

