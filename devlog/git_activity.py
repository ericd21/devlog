"""Git log parsing, isolated from the MCP server and database.

Runs `git log` via subprocess and parses commits into plain dicts, so this
module can be tested against a real throwaway git repo without touching
SQLite or the MCP server.
"""

import subprocess

_FIELD_SEP = "\x1f"  # unit separator; won't appear in normal commit text
_RECORD_SEP = "\x1e"  # record separator between commits
_PRETTY_FORMAT = _RECORD_SEP + _FIELD_SEP.join(["%H", "%an", "%aI", "%s"])


class GitActivityError(Exception):
    """Raised when commits cannot be read from the given repo path."""


def get_commits(repo_path: str, since: str) -> list[dict]:
    """Return commits in `repo_path` created since `since`, newest first.

    Each commit is a dict with keys: hash, author, date (ISO 8601), message.
    `since` accepts anything `git log --since` understands (a date, or a
    relative phrase like "yesterday" or "2 weeks ago").

    Raises GitActivityError if repo_path doesn't exist, isn't a git
    repository, or git itself fails to run. An empty list (not an error)
    means the repo is valid but has no matching commits.
    """
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", f"--pretty=format:{_PRETTY_FORMAT}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise GitActivityError(f"Could not run git in '{repo_path}': {exc}") from exc

    if result.returncode != 0:
        if "does not have any commits yet" in result.stderr:
            return []
        raise GitActivityError(
            f"git log failed in '{repo_path}': {result.stderr.strip()}"
        )

    return _parse_log_output(result.stdout)


def _parse_log_output(output: str) -> list[dict]:
    commits = []
    for record in output.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split(_FIELD_SEP)
        if len(fields) != 4:
            continue
        commit_hash, author, date, message = fields
        commits.append(
            {"hash": commit_hash, "author": author, "date": date, "message": message}
        )
    return commits
