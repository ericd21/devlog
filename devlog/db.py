"""SQLite storage layer for DevLog.

This is the only module that touches the database directly. Every other
part of the codebase that needs to read or write entries goes through the
functions here.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection to db_path, returning rows as dict-like Row objects."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the entries table if it does not already exist."""
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.commit()


def insert_entry(
    conn: sqlite3.Connection,
    project: str,
    summary: str,
    tags: list[str] | None = None,
    source: str = "manual",
    created_at: str | None = None,
) -> int:
    """Insert a new entry and return its id.

    `created_at` defaults to the current UTC time in ISO 8601 format.
    `source` must be "manual" or "git".
    """
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    tags_str = ",".join(tags) if tags else ""
    cursor = conn.execute(
        "INSERT INTO entries (project, summary, tags, created_at, source) "
        "VALUES (?, ?, ?, ?, ?)",
        (project, summary, tags_str, created_at, source),
    )
    conn.commit()
    return cursor.lastrowid


def query_entries(
    conn: sqlite3.Connection,
    project: str | None = None,
    since: str | None = None,
    until: str | None = None,
    text: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Query entries with optional filters, most recent first.

    `since`/`until` accept either a plain date ("YYYY-MM-DD") or a full ISO
    8601 timestamp. A plain date for `until` is treated as the end of that
    day, so it includes entries created any time on that date.
    `text` matches (case-insensitive) against the entry summary.
    """
    clauses = []
    params: list[str | int] = []

    if project is not None:
        clauses.append("project = ?")
        params.append(project)
    if since is not None:
        clauses.append("created_at >= ?")
        params.append(_normalize_bound(since, is_until=False))
    if until is not None:
        clauses.append("created_at <= ?")
        params.append(_normalize_bound(until, is_until=True))
    if text is not None:
        clauses.append("summary LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(text)}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM entries {where} ORDER BY created_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def _normalize_bound(value: str, *, is_until: bool) -> str:
    """Widen a plain "YYYY-MM-DD" date to cover the whole day for `until`."""
    if is_until and len(value) == 10:
        return f"{value}T23:59:59.999999"
    return value


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = d["tags"].split(",") if d["tags"] else []
    return d
