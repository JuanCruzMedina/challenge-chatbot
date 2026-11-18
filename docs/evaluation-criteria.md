# Check against the six evaluation criteria

The brief ("Multi-Source Chatbot with Intelligent Agent Orchestration") lists six conditions for a valid solution. For each one: what the code does, the evidence that can be re-run, and what is **not** proven. Run everything with `uv run pytest tests -q` (about 45 s, free: no test calls a real model).

| # | Criterion | Verdict | Strength of the evidence |
|---|---|---|---|
| 1 | Informational queries go through a centralized RAG + KG flow | Met | Tests + structure |
| 2 | Action requests always run through an MCP Server | Met | Tests + structure |
| 3 | The agent chooses autonomously between the two routes | Met | Loop tests (scripted) + 20/20 with Claude (small set) |
| 4 | No manual conditional logic (if/else, keywords) | Met for routing | Static tests |
| 5 | Modular and extensible: tools added without touching routing | Met | Tests with throwaway tools + real tools added to the server |
| 6 | The MCP Server handles all actions with correct MCP schemas | Met | Tests |

## 1. Informational queries: one centralized RAG + KG flow

- The agent has exactly one way to read knowledge: the tool `query_knowledge` (`agent/knowledge.py`). It wraps the whole LangGraph flow (plan → graph queries + document search → answer → check) of [informational-flow.md](informational-flow.md), which combines the Knowledge Graph (NetworkX) and the RAG index (Chroma) and returns a cited answer.
- Evidence: `tests/agent/test_agent_loop.py::test_a_question_is_answered_through_the_knowledge_tool_only`; the flow's own tests in `tests/flow/` (graph facts and passages become numbered, cited evidence); `tests/agent/test_isolation.py` (the knowledge side and the model layer do not import the agent).
- Seen in a real session: a question about teams produced a `query_knowledge` call whose answer mixed graph facts `[K1]` and document passages `[D2]`.
- Not proven: that the answer is *true*. `grounded` means "cites existing evidence".

## 2. Actions always through an MCP Server

- The only code that writes documentation is `actions/` (an MCP server, official `mcp` SDK, stdio). The agent does not import it (`test_the_agent_package_does_not_import_the_actions_package`) and the actions package imports no knowledge or model code (`tests/test_architecture_isolation.py`). The agent reaches the actions only as MCP tool calls over the protocol.
- Evidence: `tests/agent/test_agent_loop.py::test_an_action_request_runs_the_mcp_tool_the_model_asked_for`; `tests/actions/test_stdio_smoke.py` (a real server process); every write is in the audit log (`tests/actions/test_write_safety.py`).
- Separation: the MCP server is not part of the informational graph; a question never runs an action tool and an action never runs the flow, unless the model asks for both in one turn (`test_a_request_that_needs_both_...`).

## 3. The agent chooses autonomously

- The agent is a two-node loop (`model`, `tools`). The model receives the conversation and the tool list with descriptions and answers either with text or with tool calls. The code runs what was asked. Nothing else decides.
- Evidence: `test_the_route_does_not_depend_on_the_words_of_the_message` (the same code path for different wording), `test_a_turn_that_needs_no_tool_calls_no_tool`, `test_the_graph_has_only_a_model_step_and_a_tools_step`.
- **Honest limit.** These tests use a *scripted* model, so they prove that the **code** does not choose. They do not prove that a *real* model chooses well. `evaluation/agent.yaml` (20 turns: questions, actions, mixed, chat, unsupported) and `scripts/eval_agent.py` measure that with no judge model: run with Claude Haiku 5.5 it passed 16/16 on the first 16 turns, 19/19 after three regression turns were added and 20/20 on the current set (details and limits in the status at the end).

## 4. No manual conditional logic

- Routing code: `agent/graph.py` has one branch, `route`: *did the model's last message ask for tools?* That is the mechanics of tool calling, not an inspection of what the person wrote.
- Evidence (static, on the source): `test_the_routing_files_do_not_inspect_the_text_of_messages` (no `re`, no `.lower()`, `.startswith()`, `.find()` in the routing files); `tests/chat/test_isolation.py` (the chat does not inspect messages except `/exit`); `test_no_mcp_tool_name_appears_in_the_agent_source` (no tool is named in the agent, so there is nothing to compare names against).
- Scope of the claim: "no manual logic **in the routing**". Other code (validation of the flow's plan, argument checks in the tools) has ordinary conditionals; none of it decides between informational and action.
- Mutation check done: adding a tool name to the agent source makes the test fail.

## 5. Modular and extensible

- At the start of every turn the agent lists the server's tools again and rebuilds its loop. A tool is a module in `actions/tools/` with a `register` function; the server registers every module it finds.
- Evidence: `tests/actions/test_extensibility.py` (a new module appears and the defaults are unchanged), `tests/agent/test_mcp_toolbox.py::test_a_tool_added_to_the_servers_package_is_available_with_its_own_schema` and `tests/agent/test_agent.py::test_the_tools_are_listed_again_at_the_start_of_every_turn` (a tool added between two turns shows up in the second).
- Evidence in the tests: a tool module added to a tools package appears in the listing with its own schema and the defaults behave as before (`test_extensibility.py`); a tool added between two agent turns is visible in the second without any change to the agent (the two tests above). The agent source names no tool, and the test that checks it was mutation-checked.
- Real additions: `append_to_document` (commit `4dbd149`) was added as one function and its registration in the server's tools. `link_document` (commit `03706dc`) was added as one new module, `actions/tools/links.py`, with no change to the agent's loop or routing. A documentation-ticket tool was also added as a single new file with no change in `agent/`, `chat/`, `knowledge/` or `llm/` (commit `97cfacc`), and removed afterwards because it was not useful (`remove-ticket-tool`). The history keeps that demonstration; it is no longer part of the product.

## 6. The MCP Server handles all actions with correct schemas

- Five tools (`add_document`, `append_to_document`, `update_document`, `mark_document_obsolete`, `link_document`), each with a description that says when to use it and when **not** to, a closed JSON Schema (`additionalProperties: false`), `required` lists matching the mandatory arguments, and typed arguments (a service slug pattern, a minimum length on the path).
- Evidence: `tests/actions/test_server_discovery.py` (descriptions, closed schemas, required lists, unknown arguments rejected, invalid input as an MCP error that names the argument, a conflict as a normal result, success is not an error).
- The agent forwards the schemas exactly as the server declares them (`agent/mcp_tools.py`); it does not rewrite them.
- **Safeguards that live in the server, not in the agent** (`tests/actions/test_confirmation_and_scope.py`, `tests/actions/test_document_links.py`):
  - *Confirmation of edits.* `update_document` and `mark_document_obsolete` first return `needs_confirmation` with a diff and write nothing; the call is repeated with `confirmed: true` after the person agrees. On by default, off with `ACTIONS_CONFIRM_EDITS=off`. Creating and appending do not ask.
  - *Scope per session.* With `ACTIONS_ALLOWED_SERVICES` the server rejects a write to any other service, whatever the model asks. The PR review starts the server limited to the service of the PR.
  - *Links.* `add_document` and `link_document` write what a document is about (`about`: services, APIs, events) in its front matter. Names that do not exist in the workspace are reported as `unresolved`, not written as links. The graph reads `about` and answers which documents talk about an entity.

## What was verified by hand

- The hosted Agent Chat UI (`https://agentchat.vercel.app` against `langgraph dev`) with Claude: a question called `query_knowledge` and the answer came back with graph and document citations; a statement that contradicted the documentation (two names given as team leads) was not accepted as fact and the agent asked which was right. The same session exposed the problems fixed by `improve-search-and-edits` (no way to list teams, edits proposed on a file the tools cannot touch, repeated confirmations). A full run of the new version in the web UI is the user's step.

## Status and what is still open

- Real-model routing: `scripts/eval_agent.py` with `claude-haiku-5-5`, run on 2026-11-17: **16/16** (questions 6/6, actions 4/4, mixed 2/2, chat 2/2, unsupported 2/2), about $0.016 by the ledger's estimate. The mixed turns called `query_knowledge` first and then the write tool; chat and unsupported turns called no tool. The log is the output of `LLM_PROVIDER=anthropic uv run python scripts/eval_agent.py --min-rate 0.7`. It is a small set (16 turns, written by the project), one run and one model, so it supports "the model routes correctly on these cases", not a general rate. A second run on 2026-11-17 with 19 turns (three added after trying the chat: all teams with leads, two appends to a README) passed **19/19**, about $0.03.
- Third run on 2026-11-18, after the confirmation, scope and link changes, with 20 turns (one added for a document created with its links): **20/20**, about $0.04. The evaluation starts the server with `ACTIONS_CONFIRM_EDITS=off`, so it measures the routing of one turn, not the two-step confirmation; the confirmation was tried by hand in the chat.
- PR review with the same model (`scripts/eval_pr_review.py`, six invented pull requests): **5/6 or 6/6** depending on the run. The unstable case (update an existing document) passed 4 of 5 times when run alone.
- Nothing else is open for the six criteria. Optional extension of the brief (expose the solution as an MCP server for editors): the actions server starts from a standard stdio configuration and an MCP client lists its five tools (see the README); it was not tried inside an editor, and the informational flow is not exposed as an MCP server.
- Not measured: a local model (Ollama). Every figure above is one model, small sets written by the project.
