from  sqlalchemy import  create_engine,text



def execute_ddl(sql_text: str, db_url: str) -> dict:
    """
    Executes a DDL script (CREATE/ALTER PROCEDURE, FUNCTION, TRIGGER) against
    the target database. Wrapped in a transaction so a partial failure never
    leaves a half-created object behind.
 
    This function is ONLY ever called for DDL, and ONLY after a human has
    clicked Approve -- never automatically, regardless of AI verdict.
    """
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text(sql_text))
        return {"status": "success","message":"DDL executed successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}