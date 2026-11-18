# Proposal

## Why

The graph now reads `about` from a document's front matter and can list the documents about a service, API or event, but nothing writes it. A document created from the chat has no links, so the review of a pull request and the questions about "which documents talk about X" cannot find it. This is the second half of the document links.

## What Changes

- `add_document` takes an optional `about`: names of services, APIs or events the document is about. The server writes them in the front matter of the new document.
- The server checks the names against the workspace (the services and the APIs and events their manifests declare). Names that match nothing are not written; the result lists them as `unresolved`, so the model can fix or ask.
- A new tool `link_document` replaces the `about` list of an existing document (an empty list removes it) and returns the previous list so a mistake can be undone. It is a new module of the server; the agent is not touched.
- The prompt gains one rule, without naming a tool: when creating a document say what it is about using names known from the conversation or the knowledge tool, never invent them; when it cannot tell, ask one question with the likely options; afterwards say which links were added or left out.
- The routing evaluation gains a turn that creates a document and checks that its links are written.

## Capabilities

### Modified Capabilities
- `mcp-actions-tools`, `agent-tool-routing`.

## Impact

- `actions/workspace.py`, new `actions/front_matter.py`, `actions/tools/{documents,links}.py`, `agent/prompts.py`, `evaluation/agent.yaml`, tests, docs. The real-model run is announced first (about $0.04).

## Non-goals

- Links between documents (`[[…]]`) and backlinks.
- Features, teams or other entity types in `about`.
- Adding links to a document when it is appended to or edited (only `add_document` and `link_document` write them).
- A model that proposes links for old documents (that belongs to ingestion).
