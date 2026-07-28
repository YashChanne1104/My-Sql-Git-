# pyrefly: ignore [missing-import]
import sqlparse
# pyrefly: ignore [missing-import]
from sqlparse.sql import Statement, Comment
from enum import Enum


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

    Comments are skipped two ways because sqlparse represents them two ways:
    - single tokens tagged with ttype Comment.Single / Comment.Multiline
    - GROUPED runs of consecutive comment lines as a sqlparse.sql.Comment
      object, which has ttype=None (it's a TokenList, not a plain Token) --
      checking only ttype misses this second form entirely, letting a whole
      header comment block slip through as if it were the first real token.
    """
    sql_text = sql_text.strip()
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


if __name__ == "__main__":
    test_cases = [
        # This is the exact case that was failing -- grouped comment block before CREATE
        """/****** Object:  StoredProcedure [dbo].[usp_GetFTLGCReport] ******/
-- =============================================
-- Author     : SURAJ PATIL
-- Create date: 09/01/2024
-- =============================================
Create PROCEDURE [dbo].[test_Changes]
AS
BEGIN
    SELECT 1
END""",
        "CREATE OR ALTER PROCEDURE dbo.GetActiveOrders AS BEGIN SELECT 1 END",
        "UPDATE Orders SET Status = 'Shipped' WHERE OrderId = 5001",
        "SELECT * FROM Orders",
    ]

    for sql in test_cases:
        result = classify_sql(sql)
        print(f"[{result['type'].value:>7}] {result['reason']}")