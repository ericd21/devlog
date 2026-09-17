import sqlite3

import pytest

from devlog import db


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "devlog.db"
    connection = db.get_connection(str(db_path))
    db.init_db(connection)
    yield connection
    connection.close()


def test_init_db_creates_entries_table(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
    ).fetchone()
    assert row is not None


def test_insert_entry_returns_id_and_persists(conn):
    entry_id = db.insert_entry(conn, project="devlog", summary="Wrote schema")
    assert entry_id == 1

    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    assert row["project"] == "devlog"
    assert row["summary"] == "Wrote schema"
    assert row["source"] == "manual"


def test_insert_entry_stores_tags_joined(conn):
    db.insert_entry(conn, project="devlog", summary="x", tags=["bugfix", "urgent"])
    row = conn.execute("SELECT tags FROM entries").fetchone()
    assert row["tags"] == "bugfix,urgent"


def test_insert_entry_defaults_tags_to_empty(conn):
    db.insert_entry(conn, project="devlog", summary="x")
    row = conn.execute("SELECT tags FROM entries").fetchone()
    assert row["tags"] == ""


def test_insert_entry_rejects_bad_source(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_entry(conn, project="devlog", summary="x", source="bogus")


def test_query_entries_returns_tags_as_list(conn):
    db.insert_entry(conn, project="devlog", summary="x", tags=["a", "b"])
    results = db.query_entries(conn)
    assert results[0]["tags"] == ["a", "b"]


def test_query_entries_empty_tags_as_empty_list(conn):
    db.insert_entry(conn, project="devlog", summary="x")
    results = db.query_entries(conn)
    assert results[0]["tags"] == []


def test_query_entries_no_filters_returns_all_newest_first(conn):
    db.insert_entry(conn, project="a", summary="first", created_at="2026-01-01T10:00:00")
    db.insert_entry(conn, project="b", summary="second", created_at="2026-01-02T10:00:00")
    results = db.query_entries(conn)
    assert [r["summary"] for r in results] == ["second", "first"]


def test_query_entries_filters_by_project(conn):
    db.insert_entry(conn, project="api", summary="api work")
    db.insert_entry(conn, project="web", summary="web work")
    results = db.query_entries(conn, project="api")
    assert len(results) == 1
    assert results[0]["project"] == "api"


def test_query_entries_filters_by_text(conn):
    db.insert_entry(conn, project="api", summary="Fixed auth bug")
    db.insert_entry(conn, project="api", summary="Added rate limiter")
    results = db.query_entries(conn, text="auth")
    assert len(results) == 1
    assert "auth" in results[0]["summary"].lower()


def test_query_entries_text_search_is_case_insensitive(conn):
    db.insert_entry(conn, project="api", summary="Fixed Auth Bug")
    results = db.query_entries(conn, text="auth")
    assert len(results) == 1


def test_query_entries_text_escapes_like_wildcards(conn):
    db.insert_entry(conn, project="api", summary="100% done")
    db.insert_entry(conn, project="api", summary="totally done")
    results = db.query_entries(conn, text="100%")
    assert len(results) == 1
    assert results[0]["summary"] == "100% done"


def test_query_entries_filters_by_since_and_until(conn):
    db.insert_entry(conn, project="a", summary="jan1", created_at="2026-01-01T10:00:00")
    db.insert_entry(conn, project="a", summary="jan5", created_at="2026-01-05T10:00:00")
    db.insert_entry(conn, project="a", summary="jan10", created_at="2026-01-10T10:00:00")

    results = db.query_entries(conn, since="2026-01-02", until="2026-01-09")
    assert [r["summary"] for r in results] == ["jan5"]


def test_query_entries_until_plain_date_includes_whole_day(conn):
    db.insert_entry(
        conn, project="a", summary="late", created_at="2026-01-05T23:30:00"
    )
    results = db.query_entries(conn, until="2026-01-05")
    assert len(results) == 1


def test_query_entries_respects_limit(conn):
    for i in range(5):
        db.insert_entry(conn, project="a", summary=f"entry {i}")
    results = db.query_entries(conn, limit=2)
    assert len(results) == 2


def test_query_entries_no_matches_returns_empty_list(conn):
    results = db.query_entries(conn, project="nonexistent")
    assert results == []
