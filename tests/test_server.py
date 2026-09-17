import subprocess
import time

import pytest

import server
from devlog import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "devlog.db")


def test_add_entry_writes_row_and_confirms():
    result = server.add_entry(project="devlog", summary="Wrote add_entry tool")

    assert "Logged entry #1" in result
    assert "devlog" in result

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["project"] == "devlog"
    assert rows[0]["summary"] == "Wrote add_entry tool"
    assert rows[0]["source"] == "manual"


def test_add_entry_stores_tags():
    server.add_entry(project="devlog", summary="x", tags=["bugfix"])

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    assert rows[0]["tags"] == ["bugfix"]


def test_add_entry_strips_whitespace():
    server.add_entry(project="  devlog  ", summary="  did work  ")

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    assert rows[0]["project"] == "devlog"
    assert rows[0]["summary"] == "did work"


def test_add_entry_rejects_empty_project():
    with pytest.raises(ValueError):
        server.add_entry(project="   ", summary="did work")


def test_add_entry_rejects_empty_summary():
    with pytest.raises(ValueError):
        server.add_entry(project="devlog", summary="   ")


def test_search_entries_no_filters_returns_recent():
    server.add_entry(project="api", summary="did api work")
    server.add_entry(project="web", summary="did web work")

    result = server.search_entries()

    assert "did api work" in result
    assert "did web work" in result


def test_search_entries_filters_by_project():
    server.add_entry(project="api", summary="api thing")
    server.add_entry(project="web", summary="web thing")

    result = server.search_entries(project="api")

    assert "api thing" in result
    assert "web thing" not in result


def test_search_entries_filters_by_query_text():
    server.add_entry(project="api", summary="Fixed auth bug")
    server.add_entry(project="api", summary="Added rate limiter")

    result = server.search_entries(query="auth")

    assert "Fixed auth bug" in result
    assert "rate limiter" not in result


def test_search_entries_no_matches_returns_message():
    result = server.search_entries(project="nonexistent")
    assert result == "No entries found."


def test_search_entries_treats_empty_string_filters_as_no_filter():
    server.add_entry(project="api", summary="did work")

    result = server.search_entries(query="", project="", since="", until="")

    assert "did work" in result


def test_search_entries_caps_at_twenty():
    for i in range(25):
        server.add_entry(project="api", summary=f"entry {i}")

    result = server.search_entries()

    assert len(result.splitlines()) == 20


def test_entries_for_date_returns_matching_day(monkeypatch):
    conn = server._get_connection()
    try:
        db.insert_entry(
            conn, project="api", summary="did work", created_at="2026-01-05T10:00:00"
        )
        db.insert_entry(
            conn, project="api", summary="other day", created_at="2026-01-06T10:00:00"
        )
    finally:
        conn.close()

    result = server.entries_for_date("2026-01-05")

    assert "## 2026-01-05" in result
    assert "did work" in result
    assert "other day" not in result


def test_entries_for_date_no_entries():
    result = server.entries_for_date("2026-01-05")
    assert result == "## 2026-01-05\n\nNo entries for this day."


def test_entries_for_date_rejects_malformed_date():
    with pytest.raises(ValueError):
        server.entries_for_date("not-a-date")


def _run_git(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path):
    repo_path = tmp_path / "myrepo"
    repo_path.mkdir()
    _run_git(["git", "init"], cwd=repo_path)
    _run_git(["git", "config", "user.email", "test@example.com"], cwd=repo_path)
    _run_git(["git", "config", "user.name", "Test User"], cwd=repo_path)
    (repo_path / "a.txt").write_text("hello")
    _run_git(["git", "add", "a.txt"], cwd=repo_path)
    _run_git(["git", "commit", "-m", "Initial commit"], cwd=repo_path)
    return repo_path


def test_get_git_activity_inserts_entries_with_git_source(git_repo):
    result = server.get_git_activity(repo_path=str(git_repo), since="10 years ago")

    assert "Added 1 entries" in result

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0]["source"] == "git"
    assert "Initial commit" in rows[0]["summary"]


def test_get_git_activity_defaults_project_to_repo_dirname(git_repo):
    server.get_git_activity(repo_path=str(git_repo), since="10 years ago")

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    assert rows[0]["project"] == git_repo.name


def test_get_git_activity_uses_explicit_project(git_repo):
    server.get_git_activity(repo_path=str(git_repo), since="10 years ago", project="myapp")

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    assert rows[0]["project"] == "myapp"


def test_get_git_activity_not_a_repo_returns_message_not_raises(tmp_path):
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()

    result = server.get_git_activity(repo_path=str(plain_dir), since="1 week ago")

    assert "Could not read git activity" in result


def test_get_git_activity_no_commits_in_range(git_repo):
    time.sleep(2)

    result = server.get_git_activity(repo_path=str(git_repo), since="1 second ago")

    assert "No commits found" in result


def test_project_summary_rejects_empty_project():
    with pytest.raises(ValueError):
        server.project_summary("   ")


def test_project_summary_no_entries():
    result = server.project_summary("nonexistent")
    assert result == "## nonexistent\n\nNo entries logged for this project yet."


def test_project_summary_with_entries():
    server.add_entry(project="api", summary="Fixed bug", tags=["bugfix"])
    server.add_entry(project="api", summary="Added feature")
    server.add_entry(project="web", summary="unrelated")

    result = server.project_summary("api")

    assert "## api" in result
    assert "2 entries logged" in result
    assert "Fixed bug" in result
    assert "unrelated" not in result


def test_weekly_stats_no_entries():
    result = server.weekly_stats()
    assert result == "No entries logged in the last 7 days."


def test_weekly_stats_counts_recent_entries_by_project():
    server.add_entry(project="api", summary="a")
    server.add_entry(project="api", summary="b")
    server.add_entry(project="web", summary="c")

    result = server.weekly_stats()

    assert "| api | 2 |" in result
    assert "| web | 1 |" in result


def test_weekly_stats_excludes_entries_older_than_a_week():
    conn = server._get_connection()
    try:
        db.insert_entry(
            conn, project="api", summary="old", created_at="2020-01-01T10:00:00"
        )
    finally:
        conn.close()

    result = server.weekly_stats()

    assert result == "No entries logged in the last 7 days."


def test_weekly_standup_includes_recent_entries_and_instructions():
    server.add_entry(project="api", summary="Fixed auth bug")

    result = server.weekly_standup()

    assert "Fixed auth bug" in result
    assert "Yesterday" in result
    assert "Blockers" in result


def test_weekly_standup_handles_no_entries():
    result = server.weekly_standup()
    assert "No entries logged in the last 7 days." in result


def test_changelog_from_entries_groups_by_project():
    conn = server._get_connection()
    try:
        db.insert_entry(
            conn, project="api", summary="api work", created_at="2026-01-05T10:00:00"
        )
        db.insert_entry(
            conn, project="web", summary="web work", created_at="2026-01-06T10:00:00"
        )
    finally:
        conn.close()

    result = server.changelog_from_entries(since="2026-01-01", until="2026-01-10")

    assert "### api" in result
    assert "### web" in result
    assert "api work" in result
    assert "web work" in result


def test_changelog_from_entries_handles_no_entries():
    result = server.changelog_from_entries(since="2026-01-01", until="2026-01-10")
    assert "No entries logged in this range." in result


def test_retro_notes_includes_entries_and_instructions():
    server.add_entry(project="api", summary="Fixed a nasty bug", tags=["bugfix"])

    conn = server._get_connection()
    try:
        rows = db.query_entries(conn)
    finally:
        conn.close()
    today = rows[0]["created_at"][:10]

    result = server.retro_notes(since=today, until=today)

    assert "Fixed a nasty bug" in result
    assert "What went well" in result
    assert "Action items" in result


def test_retro_notes_handles_no_entries():
    result = server.retro_notes(since="2026-01-01", until="2026-01-10")
    assert "No entries logged in this range." in result
