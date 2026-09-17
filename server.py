"""DevLog MCP server entrypoint.

Registers tools, resources, and prompts for the DevLog personal engineering
journal, then serves them over stdio. Contains no business logic itself —
handlers parse input, delegate to the `devlog` package, and format output.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from devlog import db, git_activity, summarize

DB_PATH = Path(__file__).parent / "devlog.db"

mcp = MCPServer(
    name="devlog",
    instructions=(
        "DevLog is a personal engineering journal. Use its tools to log "
        "completed work and pull in git history, its resources to read "
        "back entries and summaries, and its prompts to draft standups, "
        "changelogs, and retro notes from logged entries."
    ),
)


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the DevLog database, creating the schema if needed."""
    conn = db.get_connection(str(DB_PATH))
    db.init_db(conn)
    return conn


def _validate_date(date: str) -> str:
    """Strip and validate a "YYYY-MM-DD" date string, raising a clear error otherwise."""
    date = date.strip()
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"date must be in YYYY-MM-DD format, got '{date}'") from exc
    return date


@mcp.tool()
def add_entry(project: str, summary: str, tags: list[str] | None = None) -> str:
    """Log a discrete piece of completed work in the DevLog journal.

    Call this whenever the user describes something they just finished —
    a bug fix, a shipped feature, a merged PR, a decision made — so it can
    be recalled later for standups, changelogs, or retro notes.

    Args:
        project: Short name identifying the project or repo this work belongs to.
        summary: One or two sentences describing what was done.
        tags: Optional labels (e.g. ["bugfix", "urgent"]) for later filtering.
    """
    project = project.strip()
    summary = summary.strip()
    if not project:
        raise ValueError("project must not be empty")
    if not summary:
        raise ValueError("summary must not be empty")

    conn = _get_connection()
    try:
        entry_id = db.insert_entry(conn, project=project, summary=summary, tags=tags)
    finally:
        conn.close()
    return f"Logged entry #{entry_id} for project '{project}'."


@mcp.tool()
def search_entries(
    query: str | None = None,
    project: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> str:
    """Search past DevLog entries by text, project, or date range.

    Call this to look up previously logged work — e.g. "what did I do on
    the api project last week" or "find entries mentioning auth". With no
    filters at all, returns the most recent entries.

    Args:
        query: Free-text search matched against entry summaries.
        project: Restrict results to this exact project name.
        since: Only entries on/after this date ("YYYY-MM-DD") or timestamp.
        until: Only entries on/before this date ("YYYY-MM-DD") or timestamp.
    """
    query = query.strip() if query and query.strip() else None
    project = project.strip() if project and project.strip() else None
    since = since.strip() if since and since.strip() else None
    until = until.strip() if until and until.strip() else None

    conn = _get_connection()
    try:
        entries = db.query_entries(
            conn, project=project, since=since, until=until, text=query, limit=20
        )
    finally:
        conn.close()
    return summarize.format_entries_list(entries)


@mcp.resource("devlog://entries/{date}")
def entries_for_date(date: str) -> str:
    """Read back a single day's DevLog entries as markdown.

    `date` must be "YYYY-MM-DD". Returns a heading for the date followed by
    one bullet per entry logged that day (project, summary, tags), or a
    plain "no entries" message if nothing was logged.
    """
    date = _validate_date(date)
    conn = _get_connection()
    try:
        entries = db.query_entries(conn, since=date, until=date)
    finally:
        conn.close()
    return summarize.format_day_markdown(date, entries)


@mcp.tool()
def get_git_activity(repo_path: str, since: str, project: str | None = None) -> str:
    """Pull commits from a local git repository into the DevLog journal.

    Call this when the user wants their journal backfilled from git history
    instead of (or in addition to) manually logging entries — e.g. "pull in
    today's commits from ~/code/api". Each commit becomes its own entry
    tagged source="git", distinguishing it from manually logged work.

    Args:
        repo_path: Absolute path to a local git repository.
        since: How far back to look, in anything `git log --since` accepts
            (e.g. "yesterday", "2026-01-01", "2 weeks ago").
        project: Project name to file these entries under. Defaults to the
            repo directory's name if not given.
    """
    repo_path = repo_path.strip()
    since = since.strip()
    if not repo_path:
        raise ValueError("repo_path must not be empty")
    if not since:
        raise ValueError("since must not be empty")

    project = project.strip() if project and project.strip() else Path(repo_path).name

    try:
        commits = git_activity.get_commits(repo_path, since)
    except git_activity.GitActivityError as exc:
        return f"Could not read git activity: {exc}"

    if not commits:
        return f"No commits found in {repo_path} since {since}."

    conn = _get_connection()
    try:
        for commit in commits:
            summary = f"{commit['message']} ({commit['hash'][:7]} by {commit['author']})"
            db.insert_entry(
                conn,
                project=project,
                summary=summary,
                source="git",
                created_at=commit["date"],
            )
    finally:
        conn.close()

    return f"Added {len(commits)} entries from git history in project '{project}'."


@mcp.resource("devlog://projects/{project}/summary")
def project_summary(project: str) -> str:
    """Read a rolling summary of all DevLog activity for one project.

    Returns entry counts, the active date range, the most-used tags, and
    the most recent entries — useful context before drafting a changelog
    or reviewing a project's history.
    """
    project = project.strip()
    if not project:
        raise ValueError("project must not be empty")

    conn = _get_connection()
    try:
        entries = db.query_entries(conn, project=project)
    finally:
        conn.close()
    return summarize.format_project_summary(project, entries)


@mcp.resource("devlog://stats/weekly")
def weekly_stats() -> str:
    """Read entry counts by project over the last 7 days as a markdown table.

    Useful for a quick pulse check on where time went recently, and as
    input for the weekly_standup prompt.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = _get_connection()
    try:
        entries = db.query_entries(conn, since=since)
    finally:
        conn.close()
    return summarize.format_weekly_stats(entries)


@mcp.prompt()
def weekly_standup() -> str:
    """Draft a standup update from the last 7 days of DevLog entries.

    Pulls the last 7 days of logged entries and asks the model to turn
    them into a Yesterday / Today / Blockers update.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = _get_connection()
    try:
        entries = db.query_entries(conn, since=since)
    finally:
        conn.close()
    formatted = summarize.format_entries_list(
        entries, empty_message="No entries logged in the last 7 days."
    )
    return (
        "Here are my DevLog entries from the last 7 days:\n\n"
        f"{formatted}\n\n"
        "Using only this information, draft a standup update with three "
        "sections — Yesterday, Today, Blockers. Group related entries "
        "together, write Yesterday in past tense, and infer a reasonable "
        "Today from any unfinished or in-progress work. If nothing "
        'suggests a blocker, write "None" under Blockers.'
    )


@mcp.prompt()
def changelog_from_entries(since: str, until: str) -> str:
    """Draft a changelog section, grouped by project, from entries in a date range.

    Args:
        since: Start of the range ("YYYY-MM-DD" or a full timestamp).
        until: End of the range ("YYYY-MM-DD" or a full timestamp).
    """
    conn = _get_connection()
    try:
        entries = db.query_entries(conn, since=since, until=until)
    finally:
        conn.close()
    formatted = summarize.format_entries_grouped_by_project(
        entries, empty_message="No entries logged in this range."
    )
    return (
        f"Here are my DevLog entries from {since} to {until}, grouped by "
        f"project:\n\n{formatted}\n\n"
        "Using only this information, draft a changelog section. Keep "
        "entries organized under their project as a heading, rewrite each "
        "one as a concise, user-facing changelog line rather than a raw "
        "commit message, and drop anything purely internal or not worth "
        "announcing."
    )


@mcp.prompt()
def retro_notes(since: str, until: str) -> str:
    """Generate retro notes from tagged DevLog entries in a date range.

    Args:
        since: Start of the range ("YYYY-MM-DD" or a full timestamp).
        until: End of the range ("YYYY-MM-DD" or a full timestamp).
    """
    conn = _get_connection()
    try:
        entries = db.query_entries(conn, since=since, until=until)
    finally:
        conn.close()
    formatted = summarize.format_entries_list(
        entries, empty_message="No entries logged in this range."
    )
    return (
        f"Here are my DevLog entries from {since} to {until} (tags in "
        f"parentheses):\n\n{formatted}\n\n"
        "Using only this information, write retro notes with three "
        "sections — What went well, What didn't, Action items. Treat tags "
        'like "bugfix" or "blocked" as signals of friction, and tags like '
        '"feature" or "shipped" as signals of things that went well. If '
        "there isn't enough signal for a section, say so briefly rather "
        "than inventing content."
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
