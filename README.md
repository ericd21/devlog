# DevLog

A local-first MCP (Model Context Protocol) server for keeping a personal
engineering journal — and letting an AI assistant query, summarize, and
draft from it.

Log what you worked on (by hand or pulled straight from git), then ask
Claude to turn a week of entries into a standup update, a changelog, or
retro notes.

This project exists as a hands-on, complete example of an MCP server that
uses all three MCP primitives — tools, resources, and prompts — for
real reasons, not just to check a box.

## Why this exists

Most MCP demos only show tools. DevLog is small enough to read end-to-end
in one sitting, but touches every primitive the protocol defines:

| Primitive | What it means in MCP | What it means in DevLog |
|---|---|---|
| **Tool** | A function the model can call to *do* something (model-controlled) | Log an entry, search entries, pull recent git commits into the log |
| **Resource** | Read-only data addressed by a URI (app/user-controlled) | A day's entries, a project's rolling summary, a weekly stats digest |
| **Prompt** | A reusable template a client can surface and fill with arguments | Draft a standup update, a changelog, or retro notes from logged entries |

## Primitives

### Tools

| Tool | Description |
|---|---|
| `add_entry(project, summary, tags)` | Log a discrete piece of completed work |
| `search_entries(query, project, since, until)` | Search past entries by text, project, or date range |
| `get_git_activity(repo_path, since, project)` | Parse `git log` for a repo and log commits as entries |

### Resources

| URI | Description |
|---|---|
| `devlog://entries/{date}` | Raw entries for a given day |
| `devlog://projects/{project}/summary` | Rolling summary of all activity on a project |
| `devlog://stats/weekly` | Entry counts by project over the last 7 days |

### Prompts

| Prompt | Description |
|---|---|
| `weekly_standup` | Turns the last 7 days of entries into a Yesterday/Today/Blockers update |
| `changelog_from_entries(since, until)` | Drafts a changelog section grouped by project |
| `retro_notes(since, until)` | Generates a What went well / What didn't / Action items retro |

## How it works

```
┌─────────────┐     stdio (JSON-RPC)     ┌──────────────┐     SQLite      ┌───────────┐
│ MCP Client   │ ◄──────────────────────► │  server.py   │ ◄─────────────► │ devlog.db │
│ (Claude)     │                          │  (this repo) │                 └───────────┘
└─────────────┘                          └──────┬───────┘
                                                  │
                                                  ▼
                                          local `git log`
```

The server runs locally over stdio. Nothing leaves your machine except
whatever the client (e.g. Claude) chooses to do with the text it gets back.

## Setup

Requires Python 3.11+.

```bash
git clone <your-repo-url>
cd devlog
pip install -e .
python server.py   # sanity check: starts and waits on stdio
```

### Connect it to Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "devlog": {
      "command": "python",
      "args": ["/absolute/path/to/devlog/server.py"]
    }
  }
}
```

Restart Claude Desktop. You should see DevLog's tools, resources, and
prompts available in the conversation.

### Connect it to a local or self-hosted LLM

`client.py` is a small standalone MCP client that spawns `server.py` over
stdio and drives it from any OpenAI-compatible chat-completions backend —
llama.cpp's `llama-server`, Ollama, vLLM, or OpenAI's own API. It's the
tool-calling loop that Claude Desktop/Code provide for you, made explicit,
so DevLog isn't limited to Anthropic's clients.

Install the extra dependency (`httpx`) it needs:

```bash
pip install -e ".[client]"
```

Then, with a backend already running — e.g. llama.cpp:

```bash
llama-server --jinja -m qwen2.5-7b-instruct-q4_k_m.gguf --port 8080
python client.py --model qwen2.5-7b-instruct
```

or against OpenAI's API:

```bash
python client.py --base-url https://api.openai.com/v1 --model gpt-4o --api-key sk-...
```

This starts a REPL:

```
Connected. 3 DevLog tools available. Type 'tools' to see available tools. Type 'exit' to quit.
you> show the latest git activity for this repo
```

`--base-url` defaults to `http://127.0.0.1:8080/v1` (llama.cpp's default);
`--api-key` is only needed for backends that require one. Tool-calling
reliability depends on the model — it needs to support structured function
calling (Qwen2.5-Instruct and Llama 3.1 do; not every local model does),
and small models are more likely to guess at arguments (e.g. a placeholder
file path) instead of asking a clarifying question, which Claude tends to
do more reliably.

### Inspect it directly

The official MCP Inspector is the fastest way to poke at the server without
a full client:

```bash
npx @modelcontextprotocol/inspector python server.py
```

## Example session

```
You: Log that I fixed the auth token refresh bug in the api project, tagged bugfix.
Claude: [calls add_entry] Logged.

You: Pull in today's commits from ~/code/api since yesterday.
Claude: [calls get_git_activity] Added 4 entries from git history.

You: Give me my standup update.
Claude: [uses weekly_standup prompt, reads devlog://entries/{date} resources]

Yesterday:
- Fixed auth token refresh bug (api)
- Merged rate-limiter PR (api)
Today:
- Continue auth work, start on session-timeout edge cases
Blockers:
- None
```

## Project structure

```
devlog/
├── server.py              # MCP server entrypoint — registers tools/resources/prompts
├── client.py              # standalone MCP client for local/self-hosted LLM backends
├── devlog/
│   ├── db.py               # all SQLite access
│   ├── git_activity.py     # git log parsing
│   ├── summarize.py        # pure functions for resource/prompt output
│   └── schema.sql
├── tests/
├── pyproject.toml
├── CLAUDE.md               # guidance for Claude Code working in this repo
├── PLAN.md                 # phased build plan
├── demo.md                 # log entries -> weekly_standup walkthrough
└── README.md
```

## Status

Phases 0-8 of PLAN.md are complete: all three tools, resources, and
prompts are implemented and tested. See PLAN.md's stretch goals for
optional follow-up work.

## License

MIT
