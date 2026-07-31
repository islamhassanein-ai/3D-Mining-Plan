"""Database preflight for run.ps1.

Verifies that the Postgres instance named by ``DATABASE_URL`` is reachable, and
creates the target database on first run if it does not exist yet. Alembic can
migrate a database but cannot create one, so without this a fresh checkout
fails at the migration step with a bare OperationalError.

Exit codes:
    0  database is reachable (it may have just been created)
    1  something is wrong; a human-readable explanation is on stderr

Run directly to check your setup:  venv\\Scripts\\python.exe backend\\preflight_db.py
"""
import os
import re
import sys


def _admin_url(url: str) -> str:
    """Same server, but pointed at the ``postgres`` maintenance database.

    CREATE DATABASE cannot run from inside the database being created, so the
    connection has to be made somewhere else on the same server.
    """
    return re.sub(r"/[^/?]+(\?|$)", r"/postgres\1", url, count=1)


def _database_name(url: str) -> str:
    match = re.search(r"/([^/?]+)(\?|$)", url)
    return match.group(1) if match else ""


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        from psycopg2.sql import SQL, Identifier
    except ImportError:
        print(
            "psycopg2 is not installed in this interpreter.\n"
            "  Fix: venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt",
            file=sys.stderr,
        )
        return 1

    try:
        psycopg2.connect(url).close()
        print("Postgres reachable")
        return 0
    except psycopg2.OperationalError as exc:
        message = str(exc).strip()
        first_line = message.splitlines()[0] if message else "connection failed"

        # Postgres reports a missing database as: database "x" does not exist
        db_name = _database_name(url)
        missing_db = "does not exist" in message and db_name and db_name in message
        if not missing_db:
            print(
                f"Cannot reach Postgres: {first_line}\n"
                f"  DATABASE_URL = {url}\n"
                "  Fix: start Postgres, or correct DATABASE_URL (a .env file next to\n"
                "       run.ps1 can hold it if your password differs from the default).",
                file=sys.stderr,
            )
            return 1

    # The server is up but the database is absent -- create it.
    print(f"database '{db_name}' does not exist -- creating it")
    try:
        conn = psycopg2.connect(_admin_url(url))
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute(SQL("CREATE DATABASE {}").format(Identifier(db_name)))
        conn.close()
    except psycopg2.Error as exc:
        print(
            f"Could not create database '{db_name}': {str(exc).strip()}\n"
            f"  Fix: create it by hand, e.g.  createdb {db_name}",
            file=sys.stderr,
        )
        return 1

    print(f"database '{db_name}' created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
