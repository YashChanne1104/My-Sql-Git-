from sqlalchemy import create_engine, text


def execute_ddl(sql_text: str, db_url: str) -> dict:
    """
    Executes a DDL script against the target database. Uses engine.begin()
    so the transaction auto-commits on success and auto-rolls-back on any
    exception -- engine.connect() alone does NOT commit in SQLAlchemy 2.0.

    Also queries DB_NAME() in the SAME connection right before executing,
    and returns it in the result -- this is a diagnostic to PROVE which
    database was actually targeted, rather than assuming the connection
    string was built correctly.
    """
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            actual_db = conn.execute(text("SELECT DB_NAME()")).scalar()
            conn.execute(text(sql_text))
        return {
            "status": "success",
            "message": "DDL executed successfully",
            "actual_database_connected": actual_db,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}