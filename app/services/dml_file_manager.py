import re
from pathlib import Path
from datetime import datetime, timezone
from ..core.config import FILE_PATH as DML_ARCHIVE_ROOT

def _sanitize_for_filename(text: str) -> str:
    return re.sub(r"[^\w.\-]", "_", text)


def _get_day_folder(date: datetime) -> Path:
    folder = DML_ARCHIVE_ROOT / date.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _entry_block(submission_id: int, sql_text: str, actor_email: str, label: str, timestamp: datetime) -> str:
    return (
        f"\n-- ===========================================\n"
        f"-- Submission ID : {submission_id}\n"
        f"-- {label:<14}: {actor_email}\n"
        f"-- Time          : {timestamp.isoformat()}\n"
        f"-- ===========================================\n"
        f"{sql_text.strip()}\n"
    )


def append_to_pending_file(submission_id: int, sql_text: str, submitted_by_email: str) -> str:
    """
    Appends this DML submission to today's pending.sql -- this is the
    LIVE outstanding list. Entries are removed from here the moment
    they're approved (see remove_from_pending_file).
    """
    now = datetime.now(timezone.utc)
    folder = _get_day_folder(now)
    pending_file = folder / "pending.sql"

    with open(pending_file, "a", encoding="utf-8") as f:
        f.write(_entry_block(submission_id, sql_text, submitted_by_email, "Submitted by", now))

    return str(pending_file)


def remove_from_pending_file(submission_id: int, submission_date: datetime) -> bool:
    """
    Strips this submission's entry out of that day's pending.sql once it's
    been approved -- keeps pending.sql showing only what's still genuinely
    outstanding. submission_date should be the ORIGINAL submission's created_at
    (not approval time), since that's which day's folder it was written into.

    If pending.sql becomes empty after removal, it's deleted entirely rather
    than left as a blank file.

    Returns True if an entry was found and removed, False if nothing matched
    (e.g. the file was already cleaned up, or this is being called twice).
    """
    folder = _get_day_folder(submission_date)
    pending_file = folder / "pending.sql"

    if not pending_file.exists():
        return False

    content = pending_file.read_text(encoding="utf-8")

    # Split on the entry marker, keeping each entry's own header attached.
    # Each entry looks like:
    #   \n-- ===...===\n-- Submission ID : N\n-- ...\n-- ===...===\n<sql>\n
    pattern = re.compile(
        r"\n-- ={10,}\n-- Submission ID : " + str(submission_id) + r"\n.*?\n-- ={10,}\n.*?(?=\n-- ={10,}\n-- Submission ID|\Z)",
        re.DOTALL
    )

    new_content, count = pattern.subn("", content)

    if count == 0:
        return False

    if new_content.strip():
        # rstrip only -- keep the leading newline intact, since the removal
        # pattern for the NEXT entry depends on every entry starting with \n
        pending_file.write_text(new_content.rstrip() + "\n", encoding="utf-8")
    else:
        pending_file.unlink()  # nothing left -- remove the empty file

    return True


def write_approved_file(submission_id: int, sql_text: str, approved_by_email: str) -> str:
    """
    Writes the standalone permanent record for one approved DML submission.
    This becomes the source of truth for that entry once it's removed from
    pending.sql.
    """
    now = datetime.now(timezone.utc)
    folder = _get_day_folder(now)
    date_str = now.strftime("%Y-%m-%d")
    safe_approver = _sanitize_for_filename(approved_by_email)

    filename = f"{date_str}_approved_by_{safe_approver}_sub{submission_id}.sql"
    filepath = folder / filename

    header = (
        f"-- ===========================================\n"
        f"-- Submission ID : {submission_id}\n"
        f"-- Approved by   : {approved_by_email}\n"
        f"-- Approved at   : {now.isoformat()}\n"
        f"-- ===========================================\n\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(sql_text.strip())
        f.write("\n")

    return str(filepath)


def write_approved_file_bulk(submissions: list[dict], approved_by_email: str) -> str:
    """
    Writes ONE combined file for a batch of DML submissions approved together
    in a single bulk-approve action. Each submission still gets its own
    clearly marked section inside the file, in the order given.

    submissions: list of {"id": int, "sql_text": str}
    Returns the file path as a string.
    """
    now = datetime.now(timezone.utc)
    folder = _get_day_folder(now)
    date_str = now.strftime("%Y-%m-%d")
    safe_approver = _sanitize_for_filename(approved_by_email)
    ids_str = "-".join(str(s["id"]) for s in submissions)

    filename = f"{date_str}_approved_by_{safe_approver}_bulk_sub{ids_str}.sql"
    filepath = folder / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(
            f"-- ===========================================\n"
            f"-- BULK APPROVAL\n"
            f"-- Approved by   : {approved_by_email}\n"
            f"-- Approved at   : {now.isoformat()}\n"
            f"-- Submissions   : {ids_str}\n"
            f"-- ===========================================\n\n"
        )
        for s in submissions:
            f.write(
                f"-- --- Submission ID : {s['id']} ---\n"
                f"{s['sql_text'].strip()}\n\n"
            )

    return str(filepath)