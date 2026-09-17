# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

DevLog is a local-first MCP (Model Context Protocol) server. It lets a
developer log daily work entries (manually or pulled from git), then exposes
that log to any MCP client (Claude Desktop, Claude Code, etc.) via three
primitives:

- **Tools** — actions the model can invoke: `add_entry`, `search_entries`,
  `get_git_activity`
- **Resources** — read-only data addressed by URI: `devlog://entries/{date}`,
  `devlog://projects/{project}/summary`, `devlog://stats/weekly`
- **Prompts** — reusable templates: `weekly_standup`,
  `changelog_from_entries`, `retro_notes`

See PLAN.md for the build sequence and README.md for user-facing docs.

## Stack

- Python 3.11+
- `mcp` official SDK (stdio transport for local dev)
- SQLite (`devlog.db`, via `sqlite3` stdlib — no ORM needed, keep it simple)
- `subprocess` for `git log` parsing (avoid adding GitPython as a dependency
  unless it clearly earns its place)
- `pytest` for tests

## Architecture conventions

- `server.py` — MCP server entrypoint, registers tools/resources/prompts,
  contains no business logic itself
- `devlog/db.py` — all SQLite access lives here; nowhere else touches the
  database directly
- `devlog/git_activity.py` — git log parsing, isolated so it's easy to test
  without a real repo (accept a repo path, return plain dicts)
- `devlog/summarize.py` — pure functions that turn rows of entries into the
  text used by resources and prompts (no I/O in this file)
- Keep tool/resource/prompt handler functions thin: parse input, call into
  `devlog/`, format output. Business logic does not belong in `server.py`.

## Coding style

- Type hints on all function signatures
- Docstrings on every tool/resource/prompt handler — these often get surfaced
  to the model as descriptions, so write them for an LLM reader, not just a
  human one
- Prefer explicit SQL over query builders
- No global mutable state beyond a single DB connection factory
- Every new tool, resource, or prompt needs: (1) a handler, (2) a docstring
  explaining when the model should use it, (3) at least one test

## Commands

```bash
# install deps
pip install -e .

# run the server directly (stdio) for manual testing
python server.py

# run tests
pytest

# inspect with the official MCP inspector
npx @modelcontextprotocol/inspector python server.py
```

## What "done" looks like for each primitive

- A **tool** is done when it has input validation, a clear docstring, and
  returns structured, model-friendly text (not raw DB rows).
- A **resource** is done when its URI is stable, documented in README.md, and
  it returns markdown or plain text the model can read directly.
- A **prompt** is done when it accepts arguments, fills a template with real
  data pulled from `devlog/`, and produces something usable as-is (a standup
  update, a changelog entry) — not just a restatement of raw entries.

## Notes for Claude Code specifically

- Work through PLAN.md phase by phase; don't jump ahead to later phases
  before earlier ones have passing tests.
- After adding or changing a tool/resource/prompt, update the "Primitives"
  table in README.md so it never drifts out of sync with the code.
- Ask before adding new third-party dependencies — this project is meant to
  stay small enough to read end-to-end in one sitting.
