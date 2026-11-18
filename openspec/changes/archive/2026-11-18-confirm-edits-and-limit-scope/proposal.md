# Proposal

## Why

Writes have no safety net. In the chat, changing or obsoleting an existing document happens at once, and with real documentation a wrong edit is costly. In the pull request review, the text of a PR is untrusted: a hostile description could push the agent to edit documents of other services, and the only protection is the prompt, which the model may not follow.

## What Changes

- **Confirmation of edits.** `update_document` and `mark_document_obsolete` take `confirmed` (default false). Without it they write nothing and return `needs_confirmation` with a diff of what would change; with `confirmed: true` they write. Creating a document and appending text stay direct, because they overwrite nothing. A conflict is still reported before any preview.
- **Scope.** The server reads `ACTIONS_ALLOWED_SERVICES` (comma separated). A write to another service fails with an error that names the allowed ones, and nothing is written. Unset means every service, as today.
- **Chat default.** The server asks for confirmation unless `ACTIONS_CONFIRM_EDITS=off`.
- **Review.** A PR review starts the server with the scope set to the service of the PR and confirmation off (the review's report and `--dry-run` are its safeguard, as decided before). The server enforces it; the prompt is not relied on.
- **Prompt.** One rule: when a tool returns a preview that needs confirmation, show it and wait; after the person agrees, repeat the call as the tool says.

## Capabilities

### Modified Capabilities
- `mcp-actions-tools`, `pr-documentation-review`, `agent-tool-routing`.

## Impact

- `actions/workspace.py`, `actions/tools/documents.py`, `agent/prompts.py`, `pr_review/{review,__main__}.py`, `scripts/eval_pr_review.py`, tests, docs. The chat needs one extra turn per edit. The real-model evaluation is rerun (announced first, about $0.03).

## Non-goals

- Confirming creation or append.
- Per-user permissions, or limiting reads.
- Letting a review touch documents of services other than the PR's.
