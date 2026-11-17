# Design

## Context

- Ready to use: `Agent` (`open`, `chat`, `tool_names`), `build_agent_graph`, `McpToolbox`, `KnowledgeService`, `AgentModelError`, and the scripted chat model (`agent/scripted_chat.py`). Behavior contracts: `specs/ui-terminal-chat/spec.md` and `specs/ui-graph-server/spec.md`; motivation in `proposal.md`.
- Decision D8 (`docs/design-decisions.md`): a passive UI with no frontend of ours, terminal first, then Agent Chat UI through `langgraph dev`. Invariants: the UI only forwards and prints; routing stays with the model.
- Agent Chat UI is a ready-made web app that talks to a LangGraph server. It can be used from its public page, with the browser connecting to `localhost:2024`; the messages do not pass through that site. Installing it locally would need Node and a large download, and the user chose not to.
- I cannot drive a browser session with the user's Ollama here, so the web side is verified up to the server's API, and the browser step is the user's.

## Goals / Non-Goals

**Goals:** a terminal chat that makes the routing visible; the same agent served for the web UI with no new logic; every behavior testable with scripted models.

**Non-Goals:** a frontend, streaming in the terminal, persistence of history, authentication, confirmations.

## Decisions

**D-1. The terminal chat is a thin loop over `Agent`.** `chat/terminal.py` has `run_chat(agent, read, write)`: `read` and `write` are injected (default `input` and `print`), so tests drive it with lists. Each turn appends the person's line to a history list, calls `agent.chat(history)`, prints `reply.text` and one line `  ↳ called: name, name` when tools were called (from `reply.tool_calls`), then extends the history with `reply.messages`. The only inspection of the line is `== "/exit"`. `AgentModelError` and `LLMUnavailableError` are printed and the loop continues; any other exception propagates. Alternative: `prompt_toolkit` or `rich`; rejected, they add dependencies for no requirement.

**D-2. The entry point.** `chat/__main__.py` parses nothing but `--workspace` (default `AGENT_DATA_ROOT`). It checks the workspace first (exit code 2 with the seed command), opens `Agent.open(...)` and runs the loop; end of input and `KeyboardInterrupt` leave cleanly, and the `async with` stops the server.

**D-3. The served graph is built by a factory from the agent's parts.** `ecosystem_assistant/chat/server_graph.py` exposes an async factory that opens the toolbox, builds the graph with `build_agent_graph(model, tools, SYSTEM_PROMPT)` and yields it, closing the server afterwards. It reuses the agent's functions and adds nothing to the graph. `langgraph.json` registers it as one graph, named `agent`. LangGraph calls a factory per run, so the tool list is re-read each time, which gives runtime discovery in the web UI too. Whether `langgraph dev` accepts an async context-manager factory, and how it passes config, is verified by a probe in task 1.2; if it does not, the fallback is an async function that returns the graph and a toolbox closed by a finalizer, with the same tests.

**D-4. Same settings as the agent.** The factory reads `OLLAMA_*`, `AGENT_DATA_ROOT` and the other variables from the environment, like `Agent.open`. `langgraph.json` points `env` at `.env`, which is git-ignored.

**D-5. Dependency.** `langgraph-cli[inmem]` as a dev dependency. The dry run installs 19 packages and changes `grpcio` 1.85.1 → 1.81.2 and `protobuf` 7.36.2 → 6.33.6; `mcp`, `langgraph`, `chromadb` are untouched. After installing, the whole suite and the data validator must be green; if anything breaks, stop and report instead of pinning around it.

**D-6. What is verified for the web UI.** With `langgraph dev` running against a scripted model (an environment variable selects it for the probe only, never default), a script posts a message to the server's HTTP API and checks that the streamed result has the tool call, the tool result and the reply. That proves everything except the browser page itself, which the user opens manually. The document says exactly this.
