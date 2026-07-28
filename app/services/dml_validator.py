import re

# Matches a three-part qualified name: database.schema.table
# e.g. ETransReporting.dbo.tblBranch, with optional [brackets] on any part.
QUALIFIED_NAME = r"\[?\w+\]?\.\[?\w+\]?\.\[?\w+\]?"


def validate_dml_syntax(sql_text: str, keyword: str) -> dict:
    """
    Enforces fully qualified three-part naming (database.schema.table) for
    DML statements -- e.g. ETransReporting.dbo.tblBranch, not just tblBranch.

    Why this matters here specifically: DML is never auto-executed by the
    app (a human always runs it manually in SSMS later, from the approved
    file). Since there's no USE statement or connection context carried
    along with that file, the script MUST be fully self-contained --
    otherwise whoever runs it manually could end up targeting the wrong
    database with no warning.

    Returns {"valid": bool, "reason": str}
    """
    sql = sql_text.strip()

    if keyword == "UPDATE":
        pattern = rf"^UPDATE\s+({QUALIFIED_NAME})\s+SET\s+.+\s+WHERE\s+.+$"
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return {
                "valid": False,
                "reason": "UPDATE must use the format: "
                          "UPDATE database.dbo.table SET ... WHERE ... "
                          "(fully qualified table name and a WHERE clause are both required)"
            }
        return {"valid": True, "reason": None}

    if keyword == "INSERT":
        pattern = rf"^INSERT\s+(INTO\s+)?({QUALIFIED_NAME})\s*\(.+\)\s*VALUES\s*\(.+\)$"
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return {
                "valid": False,
                "reason": "INSERT must use the format: "
                          "INSERT INTO database.dbo.table (columns) VALUES (values) "
                          "(fully qualified table name required)"
            }
        return {"valid": True, "reason": None}

    if keyword == "DELETE":
        pattern = rf"^DELETE\s+FROM\s+({QUALIFIED_NAME})\s+WHERE\s+.+$"
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        if not match:
            return {
                "valid": False,
                "reason": "DELETE must use the format: "
                          "DELETE FROM database.dbo.table WHERE ... "
                          "(fully qualified table name and a WHERE clause are both required)"
            }
        return {"valid": True, "reason": None}

    if keyword == "MERGE":
        # MERGE syntax varies too much to validate with a simple pattern --
        # allowed through without this specific check.
        return {"valid": True, "reason": None}

    return {"valid": True, "reason": None}
