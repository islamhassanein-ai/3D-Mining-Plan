"""Password recovery, .env persistence and URL handling in preflight_db.

Covers the branches that cannot be reached against a live local server --
remote hosts, prompt handling, and malformed input.
"""
import pytest

from backend import preflight_db as pf


# ---------------------------------------------------------------------------
# URL parsing / rebuilding
# ---------------------------------------------------------------------------

def test_parse_full_url():
    parts = pf.parse_url("postgresql://bob:s3cret@db.host:5433/mining_db")
    assert parts["scheme"] == "postgresql"
    assert parts["user"] == "bob"
    assert parts["password"] == "s3cret"
    assert parts["host"] == "db.host"
    assert parts["port"] == "5433"
    assert parts["database"] == "mining_db"


def test_parse_url_without_password():
    parts = pf.parse_url("postgresql://bob@localhost:5432/mining_db")
    assert parts["user"] == "bob"
    assert parts["password"] is None


def test_build_url_swaps_password_only():
    url = "postgresql://postgres:old@localhost:5432/mining_db"
    parts = pf.parse_url(url)
    assert pf.build_url(parts, password="new") == \
        "postgresql://postgres:new@localhost:5432/mining_db"


def test_build_url_with_empty_password_drops_the_colon():
    parts = pf.parse_url("postgresql://postgres:old@localhost:5432/mining_db")
    assert pf.build_url(parts, password="") == \
        "postgresql://postgres@localhost:5432/mining_db"


def test_build_url_swaps_database_for_the_admin_connection():
    parts = pf.parse_url("postgresql://postgres:pw@localhost:5432/mining_db")
    assert pf.build_url(parts, database="postgres") == \
        "postgresql://postgres:pw@localhost:5432/postgres"


def test_query_string_is_preserved():
    url = "postgresql://postgres:pw@localhost:5432/mining_db?sslmode=require"
    parts = pf.parse_url(url)
    assert pf.build_url(parts, password="x").endswith("?sslmode=require")


def test_redact_hides_the_password():
    out = pf.redact("postgresql://postgres:hunter2@localhost:5432/mining_db")
    assert "hunter2" not in out
    assert "****" in out


def test_redact_is_a_noop_without_a_password():
    url = "postgresql://postgres@localhost:5432/mining_db"
    assert pf.redact(url) == url


# ---------------------------------------------------------------------------
# Loopback detection -- the guard on password scanning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]", "LOCALHOST"])
def test_loopback_hosts_are_local(host):
    assert pf.is_local("postgresql://u:p@{}:5432/db".format(host)) is True


def test_unbracketed_ipv6_is_rejected_as_malformed():
    """An IPv6 literal must be bracketed to be a valid URL. Failing to parse is
    the safe outcome -- is_local() says False, so no password scanning."""
    assert pf.parse_url("postgresql://u:p@::1:5432/db") is None
    assert pf.is_local("postgresql://u:p@::1:5432/db") is False


@pytest.mark.parametrize("host", [
    "db.example.com", "10.0.0.5", "192.168.1.20", "prod-db.internal",
])
def test_non_loopback_hosts_are_not_local(host):
    assert pf.is_local("postgresql://u:p@{}:5432/db".format(host)) is False


def test_remote_server_is_never_password_scanned(monkeypatch, capsys):
    """Cycling a password list against someone else's server is credential
    guessing. Only localhost recovery is in scope."""
    scanned = []
    monkeypatch.setattr(pf, "try_common_passwords",
                        lambda url: scanned.append(url))
    monkeypatch.setattr(pf, "probe",
                        lambda url: pf.Probe(pf.Probe.BAD_PASSWORD, "nope"))

    result = pf.resolve_postgres(
        "postgresql://postgres:wrong@db.example.com:5432/mining_db",
        allow_prompt=True,
    )

    assert result is None
    assert scanned == [], "must not attempt passwords against a remote host"
    assert "only runs against localhost" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Password discovery
# ---------------------------------------------------------------------------

def test_discovery_returns_the_first_working_password(monkeypatch):
    url = "postgresql://postgres:wrong@localhost:5432/mining_db"

    def fake_probe(candidate):
        if ":root@" in candidate:
            return pf.Probe(pf.Probe.OK)
        return pf.Probe(pf.Probe.BAD_PASSWORD, "rejected")

    monkeypatch.setattr(pf, "probe", fake_probe)
    assert pf.try_common_passwords(url) == \
        "postgresql://postgres:root@localhost:5432/mining_db"


def test_discovery_accepts_a_password_whose_database_is_absent(monkeypatch):
    """A missing database still proves the credentials are right."""
    monkeypatch.setattr(pf, "probe", lambda c: (
        pf.Probe(pf.Probe.NO_DATABASE, "does not exist") if ":123456@" in c
        else pf.Probe(pf.Probe.BAD_PASSWORD, "rejected")))

    found = pf.try_common_passwords("postgresql://postgres:wrong@localhost:5432/absent_db")
    assert found == "postgresql://postgres:123456@localhost:5432/absent_db"


def test_discovery_skips_the_password_already_known_to_fail(monkeypatch):
    tried = []

    def fake_probe(candidate):
        tried.append(candidate)
        return pf.Probe(pf.Probe.BAD_PASSWORD, "rejected")

    monkeypatch.setattr(pf, "probe", fake_probe)
    pf.try_common_passwords("postgresql://postgres:admin@localhost:5432/db")

    assert not any(":admin@" in c for c in tried)


def test_discovery_stops_when_the_server_goes_away(monkeypatch):
    calls = []

    def fake_probe(candidate):
        calls.append(candidate)
        return pf.Probe(pf.Probe.UNREACHABLE, "connection refused")

    monkeypatch.setattr(pf, "probe", fake_probe)
    assert pf.try_common_passwords("postgresql://postgres:wrong@localhost:5432/db") is None
    assert len(calls) == 1, "should abort rather than retry a dead server"


def test_discovery_returns_none_when_nothing_works(monkeypatch):
    monkeypatch.setattr(pf, "probe", lambda c: pf.Probe(pf.Probe.BAD_PASSWORD, "no"))
    assert pf.try_common_passwords("postgresql://postgres:wrong@localhost:5432/db") is None


# ---------------------------------------------------------------------------
# Prompting is opt-in
# ---------------------------------------------------------------------------

def test_prompt_is_not_reached_unless_explicitly_allowed(monkeypatch, capsys):
    """sys.stdin.isatty() is unreliable on Windows (NUL reports as a tty) and
    getpass reads the console directly, so an inferred prompt would hang a
    scheduled run forever."""
    monkeypatch.setattr(pf, "probe", lambda c: pf.Probe(pf.Probe.BAD_PASSWORD, "no"))
    monkeypatch.setattr(pf, "try_common_passwords", lambda url: None)

    def explode(url):
        raise AssertionError("prompt must not run without allow_prompt")

    monkeypatch.setattr(pf, "prompt_for_password", explode)

    assert pf.resolve_postgres(
        "postgresql://postgres:wrong@localhost:5432/db", allow_prompt=False) is None
    assert "Create a .env file" in capsys.readouterr().out


def test_prompt_accepts_a_correct_password(monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "letmein")
    monkeypatch.setattr(pf, "probe", lambda c: (
        pf.Probe(pf.Probe.OK) if ":letmein@" in c
        else pf.Probe(pf.Probe.BAD_PASSWORD, "no")))

    assert pf.prompt_for_password("postgresql://postgres:wrong@localhost:5432/db") == \
        "postgresql://postgres:letmein@localhost:5432/db"


def test_blank_entry_gives_up_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr("getpass.getpass", lambda p: calls.append(p) or "")
    monkeypatch.setattr(pf, "probe", lambda c: pf.Probe(pf.Probe.BAD_PASSWORD, "no"))

    assert pf.prompt_for_password("postgresql://postgres:x@localhost:5432/db") is None
    assert len(calls) == 1


def test_prompt_stops_after_max_attempts(monkeypatch):
    calls = []
    monkeypatch.setattr("getpass.getpass", lambda p: calls.append(p) or "nope")
    monkeypatch.setattr(pf, "probe", lambda c: pf.Probe(pf.Probe.BAD_PASSWORD, "no"))

    assert pf.prompt_for_password("postgresql://postgres:x@localhost:5432/db") is None
    assert len(calls) == pf.MAX_PROMPT_ATTEMPTS


# ---------------------------------------------------------------------------
# .env persistence
# ---------------------------------------------------------------------------

def test_env_file_is_created_when_absent(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    monkeypatch.setattr(pf, "ENV_FILE", str(env))

    assert pf.write_env("postgresql://postgres:pw@localhost:5432/mining_db") is True
    assert env.read_text().strip() == \
        "DATABASE_URL=postgresql://postgres:pw@localhost:5432/mining_db"


def test_existing_keys_and_comments_survive(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# local settings\n"
        "OTHER_KEY=keepme\n"
        "DATABASE_URL=postgresql://postgres:stale@localhost:5432/mining_db\n"
        "TRAILING=alsokeep\n"
    )
    monkeypatch.setattr(pf, "ENV_FILE", str(env))

    pf.write_env("postgresql://postgres:fresh@localhost:5432/mining_db")

    lines = env.read_text().splitlines()
    assert lines == [
        "# local settings",
        "OTHER_KEY=keepme",
        "DATABASE_URL=postgresql://postgres:fresh@localhost:5432/mining_db",
        "TRAILING=alsokeep",
    ]


def test_database_url_is_appended_when_the_file_lacks_it(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER_KEY=keepme\n")
    monkeypatch.setattr(pf, "ENV_FILE", str(env))

    pf.write_env("postgresql://postgres:pw@localhost:5432/mining_db")

    lines = env.read_text().splitlines()
    assert lines[0] == "OTHER_KEY=keepme"
    assert lines[1].startswith("DATABASE_URL=")


def test_only_the_first_database_url_is_rewritten(tmp_path, monkeypatch):
    """A duplicate key would otherwise be silently reordered; last-wins in
    dotenv parsers, so leave the file's own precedence alone."""
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=one\nDATABASE_URL=two\n")
    monkeypatch.setattr(pf, "ENV_FILE", str(env))

    pf.write_env("postgresql://postgres:pw@localhost:5432/db")
    lines = env.read_text().splitlines()
    assert lines[0] == "DATABASE_URL=postgresql://postgres:pw@localhost:5432/db"
    assert lines[1] == "DATABASE_URL=two"


def test_a_recovered_password_is_persisted(tmp_path, monkeypatch):
    """The whole point of discovery: the next run must not repeat it."""
    env = tmp_path / ".env"
    monkeypatch.setattr(pf, "ENV_FILE", str(env))
    monkeypatch.setattr(pf, "try_common_passwords",
                        lambda url: "postgresql://postgres:1234@localhost:5432/db")
    monkeypatch.setattr(pf, "probe", lambda c: (
        pf.Probe(pf.Probe.OK) if ":1234@" in c else pf.Probe(pf.Probe.BAD_PASSWORD, "no")))

    resolved = pf.resolve_postgres("postgresql://postgres:wrong@localhost:5432/db")

    assert resolved == "postgresql://postgres:1234@localhost:5432/db"
    assert "DATABASE_URL=postgresql://postgres:1234@localhost:5432/db" in env.read_text()


def test_nothing_is_written_when_recovery_fails(tmp_path, monkeypatch, capsys):
    env = tmp_path / ".env"
    monkeypatch.setattr(pf, "ENV_FILE", str(env))
    monkeypatch.setattr(pf, "try_common_passwords", lambda url: None)
    monkeypatch.setattr(pf, "probe", lambda c: pf.Probe(pf.Probe.BAD_PASSWORD, "no"))

    assert pf.resolve_postgres("postgresql://postgres:wrong@localhost:5432/db") is None
    assert not env.exists()
    capsys.readouterr()
