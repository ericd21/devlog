# PLAN.md

Build plan for DevLog, an MCP server for a personal engineering journal.
Work through phases in order. Each phase should end with something runnable.

## Phase 0 — Scaffolding

- [x] `pyproject.toml` with project metadata and the `mcp` SDK as a dependency
- [x] `server.py` that starts an MCP server over stdio with no capabilities
      yet (just proves the connection works)
- [x] `devlog/__init__.py`, `devlog/db.py`, `devlog/git_activity.py`,
      `devlog/summarize.py` as empty modules
- [x] `devlog/schema.sql` with an `entries` table:
      `id, project, summary, tags, created_at, source` (source = "manual" or
      "git")
- [x] Verify: `python server.py` starts without errors; the MCP Inspector
      connects and lists zero tools/resources/prompts (confirmed with the
      real Inspector CLI once Node.js was found under the `reactjs` conda
      env: `C:\Users\edrit\miniconda3\envs\reactjs`)

## Phase 1 — Storage layer

- [x] `devlog/db.py`: `init_db()`, `insert_entry()`, `query_entries(project=None, since=None, until=None, text=None)`
- [x] Unit tests for each function using a temp SQLite file
- [x] Verify: `pytest` passes with no server involved yet

## Phase 2 — First tool: `add_entry`

- [x] Register `add_entry(project: str, summary: str, tags: list[str] = [])`
      as an MCP tool
- [x] Docstring explains it logs a discrete piece of completed work
- [x] Writes to SQLite via `devlog/db.py`, returns a confirmation string
- [x] Verify: via the real MCP Inspector CLI, called `add_entry` and
      confirmed a row appears in the database

## Phase 3 — Second tool: `search_entries`

- [x] Register `search_entries(query: str = None, project: str = None, since: str = None, until: str = None)`
- [x] Returns a formatted list of matching entries (date, project, summary)
- [x] Handles the "no filters" case (return recent entries, capped at ~20)
- [x] Verify: add a few entries, search by project and by date range,
      confirm correct results

## Phase 4 — First resource: `devlog://entries/{date}`

- [x] Register a resource template for a given day's entries
- [x] Returns markdown: date heading, then one bullet per entry with project
      and summary
- [x] Verify: requested the resource via the real MCP Inspector CLI for a
      date with entries and a date without; confirmed sensible output for
      both

## Phase 5 — Third tool: `get_git_activity`

- [x] `devlog/git_activity.py`: given a repo path and a `since` date, run
      `git log --since=... --pretty=format:...` and parse into a list of
      dicts (hash, author, date, message)
- [x] Register `get_git_activity(repo_path: str, since: str, project: str = None)`
      as a tool that parses commits and inserts them as entries with
      `source="git"`
- [x] Handle errors gracefully: not a git repo, bad path, no commits in range
- [x] Verify: this repo (devlog itself) isn't a git repo yet, so verified
      against a throwaway repo instead — 2 commits parsed and inserted with
      `source="git"` via a real MCP client call

## Phase 6 — Remaining resources

- [x] `devlog://projects/{project}/summary` — pulls all entries for a
      project, produces a short rolling summary (simple aggregation is fine;
      no LLM call needed inside the server itself)
- [x] `devlog://stats/weekly` — counts of entries by project over the last 7
      days, formatted as a small markdown table
- [x] Verify: both resources return correct output against seeded test data

## Phase 7 — Prompts

- [x] `weekly_standup` — prompt template that instructs the model to pull
      the last 7 days of entries (via the resource or tool) and produce a
      standup update in "Yesterday / Today / Blockers" format
- [x] `changelog_from_entries(since: str, until: str)` — instructs the model
      to draft a changelog section from entries in the given range, grouped
      by project
- [x] `retro_notes(since: str, until: str)` — instructs the model to
      generate "What went well / What didn't / Action items" from tagged
      entries
- [x] Verify: invoked each prompt (weekly_standup via the real MCP
      Inspector CLI; all three via a Python MCP client) with seeded
      entries — each returns coherent, data-filled, on-format instructions
      (not tested inside Claude Desktop itself, which isn't available in
      this environment)

## Phase 8 — Polish

- [x] Input validation and clear error messages on all tools
- [x] README.md primitives table matches the actual implementation
- [x] `pytest` covers `devlog/db.py`, `devlog/git_activity.py`, and
      `devlog/summarize.py` at minimum
- [x] Add a short `demo.md` or GIF showing: log a few entries → run
      `weekly_standup` → get a usable standup message

## Stretch goals (optional, do not block "done")

- [ ] Switch transport to Streamable HTTP and note the protocol version
      differences in README.md
- [ ] Tag-based filtering across tools and prompts
- [ ] A second, alternate `retro_notes` prompt tuned for solo devs vs. teams
- [ ] Export a date range to a plain markdown file on disk
