# Proposal

## Why

The agent works, but the only way to talk to it is Python code. The brief asks for a **passive, ready-made UI**: nothing of ours decides, formats or routes. We need (1) a terminal chat to try the agent right now and (2) the agent served in the form LangChain's Agent Chat UI expects, so the same agent can be used from that ready-made web UI.

## What Changes

- Add a terminal chat, `uv run python -m ecosystem_assistant.chat`. It reads a line, sends the whole conversation to the agent, prints the reply and one line per tool the model called (so routing is visible). It keeps the conversation in memory, handles `/exit`, and turns the model-server errors into the message that says what to do. It contains no routing: it forwards and prints.
- Add the agent as a LangGraph server graph: a `langgraph.json` and a graph factory so `uv run langgraph dev` serves the same agent (same tools, same loop) on `localhost:2024`. Agent Chat UI, the hosted web page, connects to that address from the browser and shows messages and tool calls. We write no frontend and do not install the UI.
- The factory lists the MCP server's tools on every run, so a tool added to the server shows up in the web UI without touching the agent.
- Add `langgraph-cli[inmem]` as a **dev** dependency of the project (local venv only). A dry run shows it downgrades `grpcio` and `protobuf` and leaves `mcp` untouched; the whole suite is re-run after installing.
- Document how to run both and what was and was not verified.

Invariant restated: the UI only forwards messages and prints replies. Informational questions still go through `query_knowledge` alone; actions only through MCP tools; the agent's code is not touched.

## Capabilities

### New Capabilities
- `ui-terminal-chat`: the terminal conversation loop and its output.
- `ui-graph-server`: the agent served as a LangGraph graph for `langgraph dev` and Agent Chat UI.

### Modified Capabilities
<!-- None: the agent package is reused as it is. -->

## Impact

- New `src/ecosystem_assistant/chat/`, a graph factory module, `langgraph.json`, tests under `tests/chat/`, `docs/chat-ui.md`.
- Dev dependency `langgraph-cli[inmem]`. No cost: the model is the local Ollama one.
- No change to the agent, the actions server or the knowledge side.

## Non-goals

- Writing or installing a web frontend (the hosted Agent Chat UI is used from the browser; opening it is manual, I cannot test a browser session here).
- Streaming token by token in the terminal, colors beyond the minimum, history persistence across runs, authentication.
- Confirmation prompts before writes.
- Measuring the real model's routing (the optional run of `eval_agent.py` stays separate).
