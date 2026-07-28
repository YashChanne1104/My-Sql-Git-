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


