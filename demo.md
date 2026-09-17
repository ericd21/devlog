# Demo: log a few entries, then get a standup update

This is a real transcript captured against the running server (an MCP
client connected over stdio) — log a few entries, then invoke the
`weekly_standup` prompt to see it pull those entries into a ready-to-use
template.

## 1. Log a few entries

```
>>> add_entry(project='api', summary='Fixed auth token refresh bug', tags=['bugfix'])
Logged entry #1 for project 'api'.

>>> add_entry(project='api', summary='Merged rate-limiter PR', tags=['feature'])
Logged entry #2 for project 'api'.

>>> add_entry(project='web', summary='Started session-timeout edge case work')
Logged entry #3 for project 'web'.
```

## 2. Run `weekly_standup`

The prompt handler pulls the last 7 days of entries via `devlog/db.py`,
formats them via `devlog/summarize.py`, and returns a filled-in template
for the model to complete:

```
>>> weekly_standup prompt output (fed to the model):
Here are my DevLog entries from the last 7 days:

- 2026-09-12 [web] Started session-timeout edge case work
- 2026-09-12 [api] Merged rate-limiter PR (feature)
- 2026-09-12 [api] Fixed auth token refresh bug (bugfix)

Using only this information, draft a standup update with three sections —
Yesterday, Today, Blockers. Group related entries together, write
Yesterday in past tense, and infer a reasonable Today from any unfinished
or in-progress work. If nothing suggests a blocker, write "None" under
Blockers.
```

## 3. A usable standup message

That prompt, completed by the model on the client side (e.g. Claude
Desktop or Claude Code), produces something like:

```
Yesterday:
- Fixed the auth token refresh bug (api)
- Merged the rate-limiter PR (api)
- Started session-timeout edge case work (web)

Today:
- Continue session-timeout edge case work (web)

Blockers:
- None
```

That's the full loop: `add_entry` writes to SQLite, `weekly_standup` reads
it back and hands the model a template already filled with real data, and
the model turns it into a message you could paste straight into standup.
