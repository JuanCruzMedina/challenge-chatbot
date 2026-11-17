# Tasks

## 1. Setup and API check

- [x] 1.1 Install `langgraph-cli[inmem]` as a dev dependency with `uv add --dev` (local venv only), then run the whole suite and the data validator; report the changes in `uv.lock` (expected: `grpcio` and `protobuf` move down). If anything breaks, stop and report.
- [x] 1.2 Check with a throwaway script outside the repo how `langgraph dev` loads a graph factory (plain function, async function, async context manager; with and without a config argument), whether the factory runs on every run, and that `langgraph.json` accepts the `env` key. Record the confirmed facts in the docstring of `chat/server_graph.py` and adjust D-3 if the fallback is needed.
- [x] 1.3 Create the skeleton `src/ecosystem_assistant/chat/{__init__,terminal,__main__,server_graph}.py` (docstrings only) and `tests/chat/`.

## 2. The terminal loop

- [x] 2.1 Write failing tests for `run_chat` with injected input and output and a scripted agent: a reply is printed with a line naming the tools called, a turn with no tool prints only the reply, the second turn receives the first question and its reply, `/exit` and end of input end the loop.
- [x] 2.2 Implement `run_chat` and make 2.1 pass.
- [x] 2.3 Write failing tests for failures: an `AgentModelError` and an `LLMUnavailableError` are printed and the next line is still processed; an unexpected exception propagates.
- [x] 2.4 Implement the error handling and make 2.3 pass.

## 3. The entry point

- [x] 3.1 Write failing tests for `python -m ecosystem_assistant.chat`: a missing workspace exits with code 2 and prints the seed command; with a seeded copy and a scripted model injected through the module's `main(argv, agent_factory)`, a session runs and no MCP server process remains afterwards (`pgrep`).
- [x] 3.2 Implement `chat/__main__.py` and make 3.1 pass.
- [x] 3.3 Write the isolation test for the chat package (no import of the actions or knowledge packages; no string inspection of messages other than `/exit`), and mutation-check it by adding a forbidden import and a `.lower()` temporarily.

## 4. The served graph

- [x] 4.1 Write failing tests for the factory: the graph has only `model` and `tools`, and the tools `query_knowledge` plus the three MCP tools; a tool package that gains a tool between two builds shows it only in the second; no server process remains after the run; invoking the graph with a scripted model returns the tool call, the tool result and the reply.
- [x] 4.2 Implement `server_graph.py` and `langgraph.json` and make 4.1 pass. A test checks that the entry in `langgraph.json` imports and builds.
- [x] 4.3 With `langgraph dev` started against a scripted model (probe-only environment variable, never the default), post a message to the server's API with a throwaway script and verify the tool call, tool result and reply arrive. Stop the server and verify no process remains. Record what was verified.

## 5. Documentation and integration

- [x] 5.1 Write `docs/chat-ui.md` (terminal usage and an example session run by a test against a scripted agent, `langgraph dev` command, the address for the web UI, what was verified and what is manual, limits) and update D8 in `docs/design-decisions.md` and the roadmap row.
- [x] 5.2 Run the whole suite, the data validator and `openspec validate add-chat-ui --strict`; verify every `#### Scenario:` has a test (list the mapping in the closing report).
- [ ] 5.3 (Manual, for the user) Open the hosted Agent Chat UI, connect it to `http://localhost:2024` with graph `agent`, and try a question and an action with the real model. Not automated; record the outcome in the documentation only if the user reports it.
