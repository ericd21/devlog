"""Pure functions that turn entry rows into human-readable text.

No I/O here — these functions take plain dicts shaped like the ones
`devlog.db.query_entries` returns, and produce the markdown/plain text used
by tool output, resources, and prompts.
"""

from collections import Counter


def format_entry_line(entry: dict) -> str:
    """Format a single entry as a one-line bullet: date, project, summary, tags."""
    date = entry["created_at"][:10]
    tags = f" ({', '.join(entry['tags'])})" if entry["tags"] else ""
    return f"- {date} [{entry['project']}] {entry['summary']}{tags}"


def format_entries_list(
    entries: list[dict], *, empty_message: str = "No entries found."
) -> str:
    """Format a list of entries as a newline-joined bullet list."""
    if not entries:
        return empty_message
    return "\n".join(format_entry_line(entry) for entry in entries)


def format_entry_bullet(entry: dict) -> str:
    """Format a single entry without its date, for use under a date heading."""
    tags = f" ({', '.join(entry['tags'])})" if entry["tags"] else ""
    return f"- [{entry['project']}] {entry['summary']}{tags}"


def format_day_markdown(date: str, entries: list[dict]) -> str:
    """Format a single day's entries as markdown: a date heading then bullets."""
    if not entries:
        return f"## {date}\n\nNo entries for this day."
    bullets = "\n".join(format_entry_bullet(entry) for entry in entries)
    return f"## {date}\n\n{bullets}"


def format_project_summary(project: str, entries: list[dict], *, recent_count: int = 5) -> str:
    """Format a rolling summary of a project: entry count, date range, top
    tags, and its most recent entries. `entries` should be all entries for
    the project, newest first (as returned by `devlog.db.query_entries`).
    """
    if not entries:
        return f"## {project}\n\nNo entries logged for this project yet."

    dates = sorted(entry["created_at"][:10] for entry in entries)
    tag_counts = Counter(tag for entry in entries for tag in entry["tags"])

    lines = [
        f"## {project}",
        "",
        f"{len(entries)} entries logged from {dates[0]} to {dates[-1]}.",
    ]
    if tag_counts:
        top_tags = ", ".join(f"{tag} ({count})" for tag, count in tag_counts.most_common(5))
        lines.append(f"Most common tags: {top_tags}")
    lines.append("")
    lines.append("Recent activity:")
    lines.extend(format_entry_bullet(entry) for entry in entries[:recent_count])
    return "\n".join(lines)


def format_entries_grouped_by_project(
    entries: list[dict], *, empty_message: str = "No entries found."
) -> str:
    """Format entries as markdown sections grouped by project, each its own bullet list."""
    if not entries:
        return empty_message

    groups: dict[str, list[dict]] = {}
    for entry in entries:
        groups.setdefault(entry["project"], []).append(entry)

    sections = []
    for project in sorted(groups):
        bullets = "\n".join(format_entry_bullet(entry) for entry in groups[project])
        sections.append(f"### {project}\n\n{bullets}")
    return "\n\n".join(sections)


def format_weekly_stats(entries: list[dict]) -> str:
    """Format entry counts by project as a markdown table. `entries` should
    already be filtered to the desired window (e.g. the last 7 days).
    """
    if not entries:
        return "No entries logged in the last 7 days."

    counts = Counter(entry["project"] for entry in entries)
    lines = ["| Project | Entries |", "|---|---|"]
    lines.extend(f"| {project} | {count} |" for project, count in counts.most_common())
    lines.append("")
    lines.append(f"Total: {len(entries)} entries in the last 7 days.")
    return "\n".join(lines)
