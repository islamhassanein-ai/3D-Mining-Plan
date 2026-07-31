"""Database preflight for run.ps1.

Resolves a working database connection before the app starts, so a fresh
checkout does not die at the migration step with a bare OperationalError.

It handles, in order:

1. ``DATABASE_URL`` already works              -> use it
2. Database absent                             -> CREATE DATABASE (alembic can
                                                  migrate one but not create one)
3. Password rejected on a LOCAL server         -> try common dev passwords, then
                                                  prompt, then write ``.env``
4. ``--sqlite``                                -> point at a local SQLite file
                                                  and build the schema

Password discovery is deliberately limited to loopback hosts. Cycling a
password list against a remote server is credential guessing against someone
else's machine; against your own localhost it is just recovering a dev setting
you already own.

The last line of stdout is always ``DATABASE_URL=<resolved url>`` so the caller
can pick up a value that changed during resolution. Everything above it is
human-readable progress.

Exit codes:
    0  a working connection was resolved
    1  it could not be; stdout explains what to do

Run directly to check your setup:
    venv\\Scripts\\python.exe backend\\preflight_db.py
"""
import argparse
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env")
SQLITE_FILE = os.path.join(REPO_ROOT, "mining_dev.db")

DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/mining_db"

# Tried in order when the configured password is rejected on a local server.
# '' covers `trust` auth and passwordless setups.
COMMON_DEV_PASSWORDS = ["postgres", "123456", "1234", "root", "admin", "password", ""]

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", ""}

MAX_PROMPT_ATTEMPTS = 3


def log(message=""):
    """Human-readable progress. Never the machine-readable final line."""
    print(message, flush=True)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"^(?P<scheme>[^:]+)://"
    r"(?:(?P<user>[^:/@]*)(?::(?P<password>[^@]*))?@)?"
    # Bracketed IPv6 literal ([::1]) or a plain host. An unbracketed IPv6
    # address is not a valid URL and is correctly rejected.
    r"(?P<host>\[[^\]]*\]|[^:/?]*)"
    r"(?::(?P<port>\d+))?"
    r"(?:/(?P<database>[^?]*))?"
    r"(?P<query>\?.*)?$"
)


def parse_url(url):
    match = _URL_RE.match(url)
    return match.groupdict() if match else None


def build_url(parts, password=None, database=None):
    """Rebuild a URL, optionally swapping the password and/or database."""
    pw = parts.get("password") if password is None else password
    db = parts.get("database") if database is None else database

    auth = ""
    if parts.get("user"):
        auth = parts["user"]
        if pw:
            auth += ":" + pw
        auth += "@"

    netloc = parts.get("host") or ""
    if parts.get("port"):
        netloc += ":" + parts["port"]

    return "{}://{}{}/{}{}".format(
        parts["scheme"], auth, netloc, db or "", parts.get("query") or ""
    )


def redact(url):
    """Same URL with the password replaced by ****, safe to print."""
    parts = parse_url(url)
    if not parts or not parts.get("password"):
        return url
    return build_url(parts, password="****")


def is_local(url):
    parts = parse_url(url)
    return bool(parts) and (parts.get("host") or "").lower() in LOOPBACK_HOSTS


# ---------------------------------------------------------------------------
# .env persistence
# ---------------------------------------------------------------------------

def write_env(url):
    """Set DATABASE_URL in the repo-root .env, preserving every other line.

    backend/src/db/session.py reads this file when DATABASE_URL is absent from
    the environment, so writing it here is what makes the setting stick.
    """
    line = "DATABASE_URL=" + url
    existing = []
    if os.path.isfile(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as fh:
                existing = fh.read().splitlines()
        except OSError as exc:
            log("  ! Could not read {}: {}".format(ENV_FILE, exc))
            return False

    replaced = False
    for i, existing_line in enumerate(existing):
        if re.match(r"^\s*DATABASE_URL\s*=", existing_line):
            existing[i] = line
            replaced = True
            break
    if not replaced:
        existing.append(line)

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as fh:
            fh.write("\n".join(existing).rstrip("\n") + "\n")
    except OSError as exc:
        log("  ! Could not write {}: {}".format(ENV_FILE, exc))
        return False

    log("  {} {} (gitignored; stores the password in plain text)".format(
        "Updated" if replaced else "Wrote", ENV_FILE))
    return True


# ---------------------------------------------------------------------------
# Connection probing
# ---------------------------------------------------------------------------

class Probe(object):
    """Outcome of one connection attempt."""
    OK = "ok"
    NO_DATABASE = "no_database"   # server reachable, credentials fine, db absent
    BAD_PASSWORD = "bad_password"
    UNREACHABLE = "unreachable"

    def __init__(self, result, detail=""):
        self.result = result
        self.detail = detail

    @property
    def password_works(self):
        return self.result in (self.OK, self.NO_DATABASE)


def probe(url):
    import psycopg2

    try:
        psycopg2.connect(url).close()
        return Probe(Probe.OK)
    except psycopg2.OperationalError as exc:
        message = str(exc).strip()
        first_line = message.splitlines()[0] if message else "connection failed"
        lowered = message.lower()

        if "password authentication failed" in lowered or "no password supplied" in lowered:
            return Probe(Probe.BAD_PASSWORD, first_line)

        parts = parse_url(url)
        db_name = (parts or {}).get("database") or ""
        if "does not exist" in lowered and db_name and db_name in message:
            return Probe(Probe.NO_DATABASE, first_line)

        return Probe(Probe.UNREACHABLE, first_line)


def create_database(url):
    """CREATE DATABASE for the target named in url, connecting via `postgres`."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.sql import SQL, Identifier

    parts = parse_url(url)
    db_name = parts["database"]
    admin_url = build_url(parts, database="postgres")

    log("  database '{}' does not exist -- creating it".format(db_name))
    try:
        conn = psycopg2.connect(admin_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute(SQL("CREATE DATABASE {}").format(Identifier(db_name)))
        conn.close()
    except psycopg2.Error as exc:
        log("")
        log("ERROR: could not create database '{}': {}".format(db_name, str(exc).strip()))
        log("  Fix: create it by hand, e.g.  createdb {}".format(db_name))
        return False

    log("  database '{}' created".format(db_name))
    return True


# ---------------------------------------------------------------------------
# Password recovery
# ---------------------------------------------------------------------------

def try_common_passwords(url):
    """Return a working URL from COMMON_DEV_PASSWORDS, or None."""
    parts = parse_url(url)
    current = parts.get("password")

    log("  password rejected -- trying common local dev passwords...")
    for candidate in COMMON_DEV_PASSWORDS:
        if candidate == current:
            continue  # already known to fail
        candidate_url = build_url(parts, password=candidate)
        result = probe(candidate_url)
        shown = repr(candidate) if candidate else "(empty)"
        if result.password_works:
            log("    {} -> works".format(shown))
            return candidate_url
        if result.result == Probe.UNREACHABLE:
            # Server went away mid-scan; no point continuing.
            log("    server became unreachable: {}".format(result.detail))
            return None
        log("    {} -> rejected".format(shown))
    return None


def prompt_for_password(url):
    """Ask the user for the password. Returns a working URL, or None.

    Prompting is opt-in via --prompt, never inferred. sys.stdin.isatty() is not
    trustworthy here: on Windows, redirecting from NUL still reports a tty
    (NUL is a character device), and getpass then reads the console handle
    directly, ignoring the redirection -- so a scheduled or piped run would
    block forever on a prompt nobody can answer.
    """
    import getpass

    parts = parse_url(url)
    log("")
    log("  None of the common passwords worked.")
    log("  Enter the password for PostgreSQL user '{}' on {} (blank to give up):".format(
        parts.get("user") or "postgres", parts.get("host") or "localhost"))

    for attempt in range(1, MAX_PROMPT_ATTEMPTS + 1):
        try:
            entered = getpass.getpass("    Password ({}/{}): ".format(
                attempt, MAX_PROMPT_ATTEMPTS))
        except (EOFError, KeyboardInterrupt):
            log("")
            return None

        if entered == "":
            return None

        candidate_url = build_url(parts, password=entered)
        result = probe(candidate_url)
        if result.password_works:
            log("    accepted")
            return candidate_url
        if result.result == Probe.UNREACHABLE:
            log("    server unreachable: {}".format(result.detail))
            return None
        log("    rejected")

    return None


def print_manual_guidance(url):
    parts = parse_url(url) or {}
    log("")
    log("ERROR: could not authenticate to PostgreSQL.")
    log("")
    log("  Create a .env file in the project root with your password:")
    log("")
    log("      DATABASE_URL=postgresql://{}:<PASSWORD>@{}:{}/{}".format(
        parts.get("user") or "postgres",
        parts.get("host") or "localhost",
        parts.get("port") or "5432",
        parts.get("database") or "mining_db"))
    log("")
    log("  That file is gitignored, and the app reads it automatically.")
    log("  Full path: {}".format(ENV_FILE))
    log("")
    log("  Don't know the password? Reset it from an admin shell:")
    log("      psql -U postgres -c \"ALTER USER postgres PASSWORD 'postgres';\"")
    log("")
    log("  Or skip PostgreSQL entirely for a quick look:")
    log("      .\\run.ps1 -UseSQLite")


# ---------------------------------------------------------------------------
# SQLite mode
# ---------------------------------------------------------------------------

def setup_sqlite():
    """Point at a local SQLite file and build the schema from the models.

    Alembic is skipped on purpose: the migrations use ALTER COLUMN and DROP
    COLUMN, which SQLite does not support outside batch mode. The models are
    the same either way, so create_all() produces an equivalent schema.

    This is for a quick look at the UI without Postgres. It is not the
    supported production path.
    """
    url = "sqlite:///" + SQLITE_FILE.replace("\\", "/")
    os.environ["DATABASE_URL"] = url

    sys.path.insert(0, REPO_ROOT)
    from backend.src.db.session import Base, engine
    import backend.src.models  # noqa: F401 -- registers every table on Base

    fresh = not os.path.isfile(SQLITE_FILE)
    Base.metadata.create_all(bind=engine)

    log("  SQLite mode: {}".format(SQLITE_FILE))
    log("  schema {} from the models (alembic is skipped -- SQLite cannot ALTER COLUMN)".format(
        "created" if fresh else "verified"))
    return url


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def resolve_postgres(url, allow_prompt=False):
    """Return a working PostgreSQL URL, or None."""
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        log("")
        log("ERROR: psycopg2 is not installed in this interpreter.")
        log("  Fix: venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt")
        return None

    result = probe(url)

    if result.result == Probe.BAD_PASSWORD:
        if not is_local(url):
            log("")
            log("ERROR: password rejected by {}".format(redact(url)))
            log("  Automatic password recovery only runs against localhost, so it is")
            log("  skipped here. Set the correct DATABASE_URL for this remote server.")
            return None

        working = try_common_passwords(url)
        if working is None and allow_prompt:
            working = prompt_for_password(url)
        if working is None:
            print_manual_guidance(url)
            return None

        write_env(working)
        url = working
        result = probe(url)

    if result.result == Probe.UNREACHABLE:
        log("")
        log("ERROR: cannot reach PostgreSQL: {}".format(result.detail))
        log("  DATABASE_URL = {}".format(redact(url)))
        log("  Fix: start PostgreSQL, or correct DATABASE_URL (a .env file next to")
        log("       run.ps1 can hold it if your password differs from the default).")
        log("")
        log("  Or skip PostgreSQL entirely for a quick look:")
        log("      .\\run.ps1 -UseSQLite")
        return None

    if result.result == Probe.NO_DATABASE:
        if not create_database(url):
            return None
        return url

    log("  Postgres reachable")
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", action="store_true",
                        help="use a local SQLite file instead of PostgreSQL")
    parser.add_argument("--prompt", action="store_true",
                        help="ask for the password interactively if the common "
                             "ones fail (only pass this from a real console)")
    args = parser.parse_args()

    if args.sqlite:
        url = setup_sqlite()
        print("DATABASE_URL=" + url)
        return 0

    url = os.environ.get("DATABASE_URL") or DEFAULT_URL
    if not parse_url(url):
        log("ERROR: DATABASE_URL is not a URL I can parse: {}".format(url))
        return 1

    resolved = resolve_postgres(url, allow_prompt=args.prompt)
    if resolved is None:
        return 1

    print("DATABASE_URL=" + resolved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
