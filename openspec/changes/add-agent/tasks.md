# Tasks

## 1. Setup and API check

- [ ] 1.1 Add `langchain-ollama` (one small package, local venv, no global install) pinned with `~=`, and create the skeleton `src/ecosystem_assistant/agent/{__init__,settings,mcp_tools,knowledge,graph,agent,prompts,records}.py` (docstrings only) and `tests/agent/`; verify the import works and the existing suite still passes.
- [ ] 1.2 Check the installed APIs with throwaway scripts outside the repo: `ChatOllama` construction and `bind_tools` with a tool built from a JSON Schema dictionary (no server); `StructuredTool` with a dictionary `args_schema` and a `ToolException` inside LangGraph's `ToolNode` (the shape of the tool message); one MCP `Client` session on the stdio parameters of the real server doing a listing and several calls inside one `async with`; and one real request through `ChatOllama` with a toy tool against the running Ollama, to see the `tool_calls` format and the error when the server is down; record the confirmed names at the top of `graph.py` and `mcp_tools.py`; verify no process is left running.

## 2. Supporting changes to the server and the seed

- [ ] 2.1 Write failing tests `tests/actions/test_tools_package_env.py` for `ACTIONS_TOOLS_PACKAGE` (the default is the real package; a temporary package with one more tool, started as a stdio subprocess with `PYTHONPATH`, lists it; an unimportable package stops the start naming it); then implement it in `server.py`; verify they pass and the existing server tests still do.
- [ ] 2.2 Write failing tests for the seed script copying the whole ecosystem (`company.yaml`, `company/`, `clients/`, `repos/`, `prs/`, the README) to the workspace, a re-seed restoring exactly that content and removing extras only among those known entries, and the refusal to touch a folder it did not create; then change `scripts/seed_workspace.py` and generalize the existing seed and documentation tests; verify the whole suite passes and `docs/actions-server.md` still describes the commands correctly.

## 3. The MCP bridge

- [ ] 3.1 Write failing tests `tests/agent/test_mcp_toolbox.py` for opening the toolbox on the real server over stdio and on an in-process server, listing tools with the name, description and input schema exactly as the server declares them, and closing without leaving the subprocess running; then implement `McpToolbox` in `mcp_tools.py`; verify they pass.
- [ ] 3.2 Write failing tests for calling the tools through the bridge: a success returns the server's text, an error result becomes a tool error with the server's message, a conflict outcome comes back unchanged as a result, and invalid arguments become a tool error; then implement the call mapping; verify they pass.
- [ ] 3.3 Write failing tests for `refresh()` on an in-process server that gains and loses tools at runtime, and for the discovery of a tool added through `ACTIONS_TOOLS_PACKAGE` over stdio, callable with its own schema; then implement `refresh()`; verify they pass.

## 4. The knowledge tool

- [ ] 4.1 Write failing tests `tests/agent/test_knowledge_service.py` for the refresh before each question (a document created in the workspace through an MCP tool is found by the next question, an edited one answers with its new text), the data left unchanged, and the audit log of the actions server left untouched; then implement `KnowledgeService` in `knowledge.py`; verify they pass.
- [ ] 4.2 Write failing tests for the `query_knowledge` LangChain tool (name, description, a single `question` argument, the compact result with answer, status, grounded flag and sources, and a model that cannot be reached propagating); then implement it; verify they pass.

## 5. The agent

- [ ] 5.1 Write failing tests `tests/agent/test_agent_loop.py` with a scripted chat model, the real MCP server and the real knowledge tool for the routing scenarios (question, action, both in order, no tool for a greeting, the same model output giving the same tools for different messages, an MCP error and a conflict reaching the model, an unknown tool reported with the available names, the cap of six tool calls); then implement the two-node graph in `graph.py` and the prompt in `prompts.py`; verify they pass.
- [ ] 5.2 Write failing tests for the `Agent` class (opening and closing, the list of tools, a turn returning the reply and the record of tool calls as JSON, refreshing the tools at the start of every turn); then implement `Agent` and `AgentReply` in `agent.py` and `records.py`; verify they pass.
- [ ] 5.3 Write failing tests for `settings.py` and the model errors with injected failing models (an unreachable server says how to start it, a model without tool support names the model, neither is replaced by another); then implement them; verify they pass.
- [ ] 5.4 Write `tests/agent/test_isolation.py`: the agent package does not import the actions package, its source contains no MCP tool name, its graph has only the model and tools nodes with a single branch on the tool requests, and the actions package does not import the agent; verify it passes and that each guard turns red when its rule is broken temporarily.

## 6. Routing evaluation

- [ ] 6.1 Write `evaluation/agent.yaml` with about sixteen turns of the five kinds (questions, actions, mixed, greetings, unsupported requests) with their expected tools and effects, and a test that every path and every tool name it mentions exists after discovery; verify it passes.
- [ ] 6.2 Write failing tests `tests/agent/test_eval_script.py` for the report (one line per turn, then the overall rate), the failure of an action tool called on a question, the effect checks in a fresh workspace per turn, and the failure status below `--min-rate`, with a scripted chat model; then implement `scripts/eval_agent.py`; verify they pass.
- [ ] 6.3 (Optional, only when the user asks for it; every other task is testable with scripted models and nothing here costs money, since the model is the local Ollama.) With the Ollama server running, run `scripts/eval_agent.py` once with the real model; verify it completes and that no turn left a process behind, and record the measured rate, the latency per kind of turn and every turn that failed, with the reason, in the documentation. If it is not run, mark it skipped and say in the documentation that the routing was measured only with scripted models.

## 7. Documentation and integration

- [ ] 7.1 Document the agent in `docs/agent.md` (the tool set, how routing happens and what the code does not do, runtime discovery and how a new MCP tool reaches the agent, the knowledge refresh, errors and the cap, settings, the evaluation and its measured numbers, limits) with worked examples run by a test against the scripted chat model, and update `docs/design-decisions.md` D3, D6 and D7 with pointers; verify every example runs as written.
- [ ] 7.2 Run the whole suite, the data validator and `openspec validate add-agent --strict`; verify all are green and every `#### Scenario:` in the spec maps to at least one test (list the mapping in the closing report).
