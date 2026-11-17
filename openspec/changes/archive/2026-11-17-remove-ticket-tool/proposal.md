# Proposal

## Why

The documentation ticket tool was added only to demonstrate that a tool can be added to the server without touching the agent. In use it turned out to be a dead end: tickets are files that nothing reads (the informational flow does not index them and no tool lists them), and the product direction is different: creating, modifying and updating documentation directly, and reviewing documentation when a pull request is merged. The user asked to remove it.

## What Changes

- Delete `actions/tools/tickets.py` and its tests; remove the tool from the lists of tools in tests and docs.
- Remove the two ticket requirements from the main specs (`mcp-actions-tools`, `agent-tool-routing`). The general extensibility requirements stay and keep their tests (throwaway tool modules added to a tools package, and a tool added between two agent turns).
- Update `docs/evaluation-criteria.md` (criterion 5) so it no longer claims the ticket as its evidence, and the roadmap and the design notes that mention tickets.
- Remove the throwaway `tickets/` folder of the local workspace (`var/`, git-ignored).

## Capabilities

### Modified Capabilities
- `mcp-actions-tools`: the ticket requirement is removed.
- `agent-tool-routing`: the ticket-specific extensibility requirement is removed.

## Impact

- Removes one file in `src/`, one test file and the ticket mentions. No agent, chat, knowledge or model code changes. History keeps the change (`add-ticket-tool` stays in the archive).

## Non-goals

- Replacing it with another tool (the next change is about writing and reviewing documentation).
- Rewriting archived changes.
