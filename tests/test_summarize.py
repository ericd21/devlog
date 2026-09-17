from devlog import summarize


def _entry(**overrides):
    base = {
        "id": 1,
        "project": "api",
        "summary": "Fixed auth bug",
        "tags": [],
        "created_at": "2026-01-05T10:00:00+00:00",
        "source": "manual",
    }
    base.update(overrides)
    return base


def test_format_entry_line_without_tags():
    line = summarize.format_entry_line(_entry())
    assert line == "- 2026-01-05 [api] Fixed auth bug"


def test_format_entry_line_with_tags():
    line = summarize.format_entry_line(_entry(tags=["bugfix", "urgent"]))
    assert line == "- 2026-01-05 [api] Fixed auth bug (bugfix, urgent)"


def test_format_entries_list_joins_multiple_entries():
    entries = [_entry(summary="first"), _entry(summary="second")]
    result = summarize.format_entries_list(entries)
    assert result == (
        "- 2026-01-05 [api] first\n- 2026-01-05 [api] second"
    )


def test_format_entries_list_empty_uses_default_message():
    assert summarize.format_entries_list([]) == "No entries found."


def test_format_entries_list_empty_uses_custom_message():
    assert summarize.format_entries_list([], empty_message="Nothing here.") == "Nothing here."


def test_format_entry_bullet_omits_date():
    bullet = summarize.format_entry_bullet(_entry())
    assert bullet == "- [api] Fixed auth bug"


def test_format_entry_bullet_with_tags():
    bullet = summarize.format_entry_bullet(_entry(tags=["bugfix"]))
    assert bullet == "- [api] Fixed auth bug (bugfix)"


def test_format_day_markdown_with_entries():
    entries = [_entry(summary="first"), _entry(project="web", summary="second")]
    result = summarize.format_day_markdown("2026-01-05", entries)
    assert result == (
        "## 2026-01-05\n\n- [api] first\n- [web] second"
    )


def test_format_day_markdown_empty():
    result = summarize.format_day_markdown("2026-01-05", [])
    assert result == "## 2026-01-05\n\nNo entries for this day."


def test_format_project_summary_no_entries():
    result = summarize.format_project_summary("api", [])
    assert result == "## api\n\nNo entries logged for this project yet."


def test_format_project_summary_includes_count_and_date_range():
    entries = [
        _entry(created_at="2026-01-10T10:00:00", summary="newer"),
        _entry(created_at="2026-01-01T10:00:00", summary="older"),
    ]
    result = summarize.format_project_summary("api", entries)
    assert "## api" in result
    assert "2 entries logged from 2026-01-01 to 2026-01-10." in result


def test_format_project_summary_includes_top_tags():
    entries = [
        _entry(tags=["bugfix"]),
        _entry(tags=["bugfix"]),
        _entry(tags=["feature"]),
    ]
    result = summarize.format_project_summary("api", entries)
    assert "Most common tags: bugfix (2), feature (1)" in result


def test_format_project_summary_omits_tags_line_when_untagged():
    result = summarize.format_project_summary("api", [_entry()])
    assert "Most common tags" not in result


def test_format_project_summary_lists_recent_entries():
    entries = [_entry(summary="newest"), _entry(summary="older")]
    result = summarize.format_project_summary("api", entries)
    assert "Recent activity:" in result
    assert "- [api] newest" in result
    assert "- [api] older" in result


def test_format_project_summary_caps_recent_entries():
    entries = [_entry(summary=f"entry {i}") for i in range(10)]
    result = summarize.format_project_summary("api", entries, recent_count=3)
    recent_section = result.split("Recent activity:\n", 1)[1]
    assert len(recent_section.splitlines()) == 3


def test_format_entries_grouped_by_project_empty():
    result = summarize.format_entries_grouped_by_project([])
    assert result == "No entries found."


def test_format_entries_grouped_by_project_groups_and_sorts_headings():
    entries = [
        _entry(project="web", summary="web work"),
        _entry(project="api", summary="api work 1"),
        _entry(project="api", summary="api work 2"),
    ]
    result = summarize.format_entries_grouped_by_project(entries)
    assert result == (
        "### api\n\n"
        "- [api] api work 1\n"
        "- [api] api work 2\n\n"
        "### web\n\n"
        "- [web] web work"
    )


def test_format_weekly_stats_no_entries():
    assert summarize.format_weekly_stats([]) == "No entries logged in the last 7 days."


def test_format_weekly_stats_counts_by_project():
    entries = [
        _entry(project="api"),
        _entry(project="api"),
        _entry(project="web"),
    ]
    result = summarize.format_weekly_stats(entries)
    assert "| api | 2 |" in result
    assert "| web | 1 |" in result
    assert "Total: 3 entries in the last 7 days." in result
