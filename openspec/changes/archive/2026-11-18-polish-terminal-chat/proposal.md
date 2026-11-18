# Proposal

## Why

The agent answers in markdown (tables, bold, lists, diffs for the edit preview) and the terminal prints it raw, so a table of teams shows as rows of pipes and a preview diff is hard to read. The line that names the called tools has the same weight as the answer.

## What Changes

- The reply is rendered as markdown with `rich` (tables, bold, lists, code blocks). The text itself is never inspected: it is handed to the renderer as it is.
- The line of called tools and the greeting are printed dimmed; errors are printed in red.
- `rich` becomes a direct dependency of the project (it is already installed as a dependency of `chromadb`; nothing new is downloaded).
- Without a terminal (a pipe, a test) the output stays plain text, as today.
- The `[K1]` / `[D2]` citation markers stay as the model wrote them: they are the evidence ids a person checks, and dimming them would need a search in the text, which the chat must not do.

## Capabilities

### Modified Capabilities
- `ui-terminal-chat`.

## Impact

- `chat/terminal.py` (two optional output functions), new `chat/render.py`, `chat/__main__.py`, `pyproject.toml`, `uv.lock`, tests, `docs/chat-ui.md`.

## Non-goals

- Streaming the reply token by token.
- Saving the conversation between sessions.
- Colors or layout for the web UI, which is a ready-made one.
