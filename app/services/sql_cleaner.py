import re


def extract_target_database(sql_text: str) -> str | None:
    """
    Pulls the database name out of a USE statement, e.g.
    'USE [ETransReporting]' or 'USE ETransReporting' -> 'ETransReporting'.
    Returns None if no USE statement is present.
    """
    match = re.search(r"^\s*USE\s+\[?(\w+)\]?\s*$", sql_text, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else None


def clean_sql_script(sql_text: str) -> str:
    """
    Strips SSMS-generated boilerplate that isn't valid inside a single
    executable batch: USE statements, GO batch separators, and the
    ANSI_NULLS/QUOTED_IDENTIFIER SET lines that SSMS auto-adds.

    USE is stripped from the SQL TEXT itself (since it can't share a batch
    with CREATE PROC/FUNCTION/TRIGGER), but the database name it specified
    should be captured separately via extract_target_database() BEFORE
    calling this, so the executor can connect to the right database instead
    of silently defaulting to whatever's in the connection string.
    """
    lines = sql_text.splitlines()
    cleaned_lines = []

    go_pattern = re.compile(r"^\s*GO\s*$", re.IGNORECASE)
    use_pattern = re.compile(r"^\s*USE\s+.+$", re.IGNORECASE)
    ansi_nulls_pattern = re.compile(r"^\s*SET\s+ANSI_NULLS\s+(ON|OFF)\s*$", re.IGNORECASE)
    quoted_id_pattern = re.compile(r"^\s*SET\s+QUOTED_IDENTIFIER\s+(ON|OFF)\s*$", re.IGNORECASE)

    for line in lines:
        if go_pattern.match(line) or use_pattern.match(line) or \
           ansi_nulls_pattern.match(line) or quoted_id_pattern.match(line):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def swap_database_in_url(db_url: str, new_database: str) -> str:
    """
    Replaces the database name in a mssql+pyodbc connection URL, keeping the
    same server/credentials/driver options. Used when a script's USE statement
    targets a different database than the one baked into DEV_DB_URL/UAT_DB_URL.

    e.g. '...@192.168.1.215:23318/master?driver=...' with new_database='ETransReporting'
      -> '...@192.168.1.215:23318/ETransReporting?driver=...'
    """
    match = re.match(r"^(.+?://[^/]+)/([^?]+)(\?.*)?$", db_url)
    if not match:
        raise ValueError(f"Could not parse database URL to swap database name: {db_url}")

    prefix, _old_db, suffix = match.groups()
    suffix = suffix or ""
    return f"{prefix}/{new_database}{suffix}"


_BLOCK_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_PATTERN = re.compile(r"--[^\n]*")
_GO_LINE_PATTERN = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
_USE_LINE_PATTERN = re.compile(r"^\s*USE\s+.+$", re.IGNORECASE | re.MULTILINE)
_SET_ON_OFF_LINE_PATTERN = re.compile(r"^\s*SET\s+\w+\s+(ON|OFF)\s*$", re.IGNORECASE | re.MULTILINE)


def strip_for_classification(sql_text: str) -> str:
    """
    Produces a classification-only view of the SQL: strips block comments,
    line comments, USE statements, GO separators, and SET ON/OFF lines.

    This exists because sqlparse's comment grouping is sensitive to
    surrounding whitespace -- after clean_sql_script removes GO/USE/SET
    lines it can leave blank lines that cause sqlparse to NOT group
    consecutive '--' divider lines as a single Comment object, letting
    something like '-- ====================' slip through as if it were
    the first real token. Stripping with regex first sidesteps that
    entirely, regardless of SSMS header boilerplate shape.

    Does NOT touch the original sql_text used for storage, review, or
    execution -- this is purely a classification input.
    """
    text = _BLOCK_COMMENT_PATTERN.sub("", sql_text)
    text = _LINE_COMMENT_PATTERN.sub("", text)
    text = _GO_LINE_PATTERN.sub("", text)
    text = _USE_LINE_PATTERN.sub("", text)
    text = _SET_ON_OFF_LINE_PATTERN.sub("", text)

    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines).strip()


