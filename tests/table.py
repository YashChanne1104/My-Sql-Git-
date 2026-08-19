# create_tables.py (run once from project root)
from app.core.database import Base, engine
from app.models import user, submission, audit_log  # import every model module so SQLAlchemy registers them

Base.metadata.create_all(bind=engine)
print("Tables created in sql_deploy_gate schema.")