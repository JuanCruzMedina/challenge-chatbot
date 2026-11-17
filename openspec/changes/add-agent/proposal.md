# Proposal

## Why

The informational flow and the MCP actions server exist, but nothing connects a person's words to them. The challenge's central requirement is an agent that **decides by itself**, through tool-calling and with no `if/else` or keyword routing, whether a request is a question (the informational flow) or an action (the MCP Server), and that adapts to new MCP tools without any change to its logic.

## What Changes

- Add an agent: a language model with tool-calling over a small LangGraph loop (model, tools). Which tool it calls, if any, is the model's decision. The only code that looks at the model's output is the standard check "did it ask for a tool?".
- The agent has exactly two kinds of tools:
  - **One knowledge tool**, `query_knowledge`, that wraps the informational flow. Before each question it refreshes the graph and the index from the data, so a document changed a moment ago is already found.
  - **The MCP tools, discovered at runtime** by an MCP client that lists them over stdio and turns their schemas into tools. No tool is named in the agent's code, so a tool added to the server appears with its schema and needs no change here.
- Tool failures (an MCP error, an unknown tool) go back to the model as tool messages, so it can correct itself or explain. A turn is capped at six tool calls.
- Add `ACTIONS_TOOLS_PACKAGE` to the actions server so tests can start it with another tools package.
- The seed script copies the whole sample ecosystem (company, clients, repos), so the workspace the MCP writes to is also a complete data root the knowledge side can read.
- Add a routing evaluation: conversational turns with the tools expected and, for actions, the effect expected on the workspace, plus a script that reports them.

Routing invariant restated (see `openspec/config.yaml`): informational queries go only through the flow; actions go only through the MCP Server; the agent never writes data itself and never imports the actions package.

## Capabilities

### New Capabilities
- `agent-tool-routing`: the agent's tool set, model-driven routing, runtime discovery of MCP tools, error handling, refresh of knowledge, and the routing evaluation.

### Modified Capabilities
<!-- None: the actions server only gains a configuration variable and the seed script copies more. -->

## Impact

- New package `ecosystem_assistant.agent`, tests under `tests/agent/`, `evaluation/agent.yaml`, `scripts/eval_agent.py`.
- New dependency `langchain-ollama` (one small package, local venv). `langchain-mcp-adapters` is not used: it would downgrade `mcp` to 1.x and break the server.
- Small edits to `ecosystem_assistant.actions.server` (one variable) and `scripts/seed_workspace.py`.
- No cost: the model is the Ollama one already installed.

## Non-goals

- The chat interface (the next change) and streaming.
- Confirmation prompts before writes: the workspace is a throwaway copy and the brief asks for automatic calls.
- Long-term memory, several MCP servers, authentication.
- Keeping documents added from the chat known to the graph (ingestion change).
- Tuning prompts beyond a baseline.
