import sqlite3
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _sqlite_enforce_foreign_keys(dbapi_connection, connection_record):
    # The app runs on PostgreSQL, which always enforces FKs. SQLite does not
    # unless asked, so without this the suite silently passes FK-ordering bugs.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()