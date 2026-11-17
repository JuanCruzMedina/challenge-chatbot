# Proposal

## Why

In a real run of the review (PR-301, dry run) the model made three update calls but only two documents changed. The third call ended in a `conflict` (the quoted text was not found), which the server reports as a normal result, so the report did not mark it. A reader of the report could not tell which calls wrote something. The model's own explanation also overstated what it changed.

## What Changes

- The report gives each tool call a status derived from its result: `failed` when the tool reported an error, `conflict` when the result says the outcome was `conflict` (nothing written), `ok` otherwise. The text report shows it next to the call.
- The report states in one line how many write calls did not write anything, so the model's explanation can be compared with the diffs.

## Capabilities

### Modified Capabilities
- `pr-documentation-review`: the report marks calls that did not write.

## Impact

- `pr_review/review.py`, tests, `docs/pr-review.md`. No change to the agent, the tools or the model's prompt.

## Non-goals

- Retrying a conflict automatically (the model already receives the conflict and may retry within its turn).
- Judging whether the model's explanation matches the diffs.
- Naming any tool in the package: the status comes from the result's own `outcome` field.
