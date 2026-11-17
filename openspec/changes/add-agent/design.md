# Design

## Context

- Ready to use: the informational flow (`InformationalFlow.ask`), the MCP actions server (three tools over stdio), the model layer, and Ollama with `qwen2.5:7b-instruct` installed and measured. Behavior contract: `specs/agent-tool-routing/spec.md`; motivation: `proposal.md`.
- Decisions D3 (LangGraph), D6 (MCP Server is the only way to act) and D7 (the agent routes by tool-calling, tools discovered dynamically, no `if/else`) in `docs/design-decisions.md` apply.
- `langchain-mcp-adapters` would downgrade the `mcp` SDK to 1.x (found with a dry run) and break the server, so the bridge from MCP to LangChain tools is written here; it is small.
- The MCP server loads its tool modules when it starts. So "a tool added to the server" reaches the agent when the server (re)starts or when the agent lists again; either way the agent's code does not change.
- The actions write to the workspace and the knowledge side reads a data root. For a document written from the chat to be found, they must be the same folder, so the workspace has to be a complete copy of the ecosystem (D-6).

## Goals / Non-Goals

**Goals:**
- Routing that is demonstrably the model's: the agent has no knowledge of what a question or an action is.
- A tool set that is discovered, never listed, so extensibility is a property of the structure.
- Failures that the model can see and react to; a bounded loop.
- Measured routing quality with the real local model.

**Non-Goals:**
- The chat interface, streaming, confirmations, long-term memory, several MCP servers.

## Decisions

**D-1. A hand-written ReAct loop on LangGraph.** `StateGraph` over LangChain messages with two nodes: `model` (the chat model with the tools bound) and `tools` (LangGraph's `ToolNode`, which runs the requested tools and turns failures into tool messages). Edges: start to `model`; after `model`, to `tools` when the last AI message has tool calls, otherwise to the end; `tools` back to `model`. That one branch is "did the model ask for a tool?", the standard loop, and it never looks at the user's words. A counter of tool calls per turn sends the loop to a final message after six. Alternatives: the prebuilt agent helpers of LangGraph/LangChain (their location and deprecations are moving, and they hide the structure the evaluation wants to show).

**D-2. The chat model is `ChatOllama`** from `langchain-ollama`, with the same `OLLAMA_*` settings as the flow and temperature 0. Tests inject any LangChain chat model; a small scripted one (a `BaseChatModel` that replays messages with tool calls and accepts `bind_tools`) lives in the tests. An unreachable server and a model without tool support are caught and re-raised as `AgentModelError` that says what to do.

**D-3. The MCP bridge (`McpToolbox`).** An async context manager that opens an MCP `Client` on a target (the stdio parameters of our server, or an in-process server in tests) and keeps the session open. `tools()` lists the server's tools and builds one LangChain `StructuredTool` each, with the server's name, description and **JSON Schema as the argument schema**. A call goes to `call_tool`; the text content of the result is returned as is (so a `conflict` outcome reaches the model unchanged); an error result raises a `ToolException` with the server's message, which `ToolNode` returns to the model as an error tool message. `refresh()` lists again. The agent calls `refresh()` at the start of every turn, so the tool set always follows the server.

**D-4. The knowledge tool.** `query_knowledge(question)` calls a `KnowledgeService` that, for every question, rebuilds the graph from the data root (a few milliseconds here), runs `index.sync` (a hash comparison; only changed files are embedded) and then asks the informational flow. The result handed to the model is compact JSON: the flow's answer, status, grounded flag and the sources of each citation, with an instruction in the tool description to relay it faithfully. Refreshing on each question is what makes the system "keep itself up to date" without a trigger; the ingestion change can still add triggers for PRs.

**D-5. A neutral system prompt.** It says what the agent is for, that tools exist, that `query_knowledge` is for questions about facts and documentation, that other tools change things and are used only when the person asks for a change, that a request no tool can do is declined, and that tool results must not be invented or altered. It names no MCP tool; their own descriptions (which already say when not to use them) do the rest.

**D-6. One folder for both sides.** `seed_workspace.py` copies the whole sample ecosystem (`company.yaml`, `company/`, `clients/`, `repos/`, `prs/`, the README) to `var/workspace`, and deletes on a re-seed only those known entries, still only in a folder it created. The agent uses that folder as the MCP workspace (`DOCS_WORKSPACE`) and as the knowledge data root. If it does not exist the agent stops with the command that creates it.

**D-7. `ACTIONS_TOOLS_PACKAGE`.** The server's `main()` reads this variable (default the real package) and builds the server with it. It exists so a test can start the real server over stdio with a different tools package.

**D-8. A turn returns an `AgentReply`.** The text of the final message and a record per tool call (name, arguments, result, whether it failed), with `to_dict()`. The UI and the evaluation read the same record.

**D-9. Routing evaluation.** `evaluation/agent.yaml` lists turns of kinds `question`, `action`, `mixed`, `chat` and `unsupported`, each with the tools expected and, for actions, a file effect expected in the workspace. The script runs each turn in a fresh seeded workspace, so an action in one turn cannot influence another. A question that triggers any MCP tool is a failure by itself.

## Risks / Trade-offs

- **A 7B model picks the wrong tool or writes wrong arguments** → errors reach the model so it can retry; the evaluation measures it; it is the known weak point of small models.
- **Latency**: an informational question costs the agent's choice, the flow's two calls and the agent's relay, so about four model calls (an estimate; measured in task 6.3).
- **The relay can distort the flow's answer** → the prompt and the tool description ask for faithful relay, the citations travel in the record, and the evaluation checks the key facts.
- **A write made by mistake** → it goes to a throwaway workspace, every write is audited, and re-seeding resets it.
- **The server subprocess must not outlive the agent** → the toolbox closes it on exit and tests check no process is left.
- **LangChain and langgraph APIs move** → versions pinned and the used pieces verified first (task 1.2).
