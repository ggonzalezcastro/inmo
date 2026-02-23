from sqlalchemy import create_mock_engine
from app.models.base import Base
from app.models.lead import Lead

def dump(sql, *multiparams, **params):
    print(sql.compile(dialect=engine.dialect))

engine = create_mock_engine("sqlite://", dump)

print("--- DDL for Lead ---")
Base.metadata.create_all(engine, tables=[Lead.__table__])
