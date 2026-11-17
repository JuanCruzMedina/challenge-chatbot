# Spec Delta

## Purpose

Defines how the same agent is served as a LangGraph graph so that the ready-made Agent Chat UI can use it through `langgraph dev`.

## ADDED Requirements

### Requirement: The served graph is the agent's own loop
The project SHALL provide a `langgraph.json` that registers one graph, built by a factory from the agent package's own loop, tools and system prompt. The served graph MUST have the same two nodes as the agent's loop and MUST NOT add a node, a branch or a tool of its own.

#### Scenario: The configuration points at a graph that can be built
- **GIVEN** the `langgraph.json` of the project
- **WHEN** its graph entry is imported and built
- **THEN** the graph has the nodes `model` and `tools` only
- **AND** it has the tools `query_knowledge` and the three MCP tools

### Requirement: Tools are discovered on every run
The graph factory SHALL list the MCP server's tools each time it builds the graph, and SHALL stop the MCP server when the run ends.

#### Scenario: A tool added to the server appears in the next run
- **GIVEN** a server whose tools package gains a tool between two builds
- **WHEN** the factory builds the graph twice
- **THEN** the second graph has the new tool and the first did not

#### Scenario: No server process is left behind
- **GIVEN** a graph built and used by the factory
- **WHEN** the run ends
- **THEN** no MCP server process remains

### Requirement: Messages travel in the standard shape
The served graph SHALL accept and return the standard `messages` state, so that tool calls and tool results are visible to a generic chat client.

#### Scenario: A run returns the tool messages
- **GIVEN** the served graph and a scripted model that calls `query_knowledge`
- **WHEN** it is invoked with a human message
- **THEN** the returned messages include the model's tool call, the tool result and the final reply

### Requirement: Running the server needs no new global installation
The project SHALL declare `langgraph-cli[inmem]` as a development dependency installed in the project's environment, and documentation SHALL state the command to start the server and the address the web UI connects to.

#### Scenario: The documented command is the one in the project
- **GIVEN** `docs/chat-ui.md`
- **WHEN** its start command and address are compared with `langgraph.json` and the dev dependency
- **THEN** they agree
