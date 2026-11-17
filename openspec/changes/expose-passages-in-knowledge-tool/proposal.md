# Proposal

## Why

To update an existing document the agent must quote its current text: `update_document` replaces a passage that has to appear exactly once. Today `query_knowledge` returns only a synthesized answer and the labels of its sources, so the agent cannot see the text. In a real session it asked the user to paste a file because of that. The same gap blocks the documentation review of pull requests (next change).

## What Changes

- The flow's answer carries the document passages it retrieved (up to the existing limit of five): path, heading path and the passage text exactly as it is in the file.
- The `query_knowledge` tool result adds a `passages` list with that data. A passage longer than 1,500 characters is cut and marked as truncated, so it is never presented as exact.
- The tool description says the passages can be used to quote text for an edit. The agent's prompt gains one rule: when changing an existing document, quote its text from the passages of the knowledge tool; if the passage needed is not among them, ask the knowledge tool again for that section; never invent the text to replace.
- Everything stays in the single informational flow: no new tool, no read inside the MCP server.

## Capabilities

### Modified Capabilities
- `knowledge-flow-answers`: the answer exposes its retrieved passages.
- `agent-tool-routing`: the knowledge tool returns them, and the prompt rule.

## Impact

- `knowledge/flow/answer.py` (and where the answer is built), `agent/knowledge.py`, `agent/prompts.py`, tests, docs. More tokens per question (at most five passages of 1,500 characters); the real cost is measured in the optional run of the routing evaluation, announced first.

## Non-goals

- A tool that reads files, or reading `service.yaml` or other non-markdown files.
- Changing how passages are retrieved or ranked.
- Guaranteeing the model quotes correctly: a wrong quote already ends in the update tool's `conflict` result, which tells the model to retry.
