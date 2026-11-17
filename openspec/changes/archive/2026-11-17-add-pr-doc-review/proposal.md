# Proposal

## Why

Documentation goes stale when code changes. The wish: when a pull request is merged, check whether documentation about that behavior exists, from a business and key-logic point of view, not line by line; add it if there is none, update it if it exists and the change warrants it, and leave it alone when it does not (a refactor, a rename, a test, a typo).

## What Changes

- New package `ecosystem_assistant/pr_review/` with `review_pull_request(pr, ...)` and a command, `python -m ecosystem_assistant.pr_review <pr.yaml> [--dry-run]`, meant to be called by CI at merge time.
- A pull request is read from a file in the format of the sample `prs/*/pr.yaml` (id, repo, title, description, changed files with status and an optional patch). Fetching a real PR from GitHub is out of scope.
- The review **runs the same agent** with a review prompt: the agent checks the service's documentation with `query_knowledge`, and creates or edits `.md` documents through the MCP tools, or does nothing. The decision is the model's by tool calling; the package has no keyword or rule that decides (a test checks it). Its prompt asks for the macro view and lists what does not deserve a change.
- The result is a report built by code from what happened: every tool call other than the knowledge tool, a unified diff per changed file, and the model's explanation. With `--dry-run` the review works on a scratch copy of the workspace, so the report is a proposal and nothing real changes.
- A review set `evaluation/pr_review/` (about six invented PRs: new behavior with no document, a changed behavior with a document, a refactor, a tests-only change, a typo, a dependency bump) and `scripts/eval_pr_review.py`, graded by effects on the files with no judge model.
- A documented CI example calling the command, **not installed** anywhere.

## Capabilities

### New Capabilities
- `pr-documentation-review`: the review of a merged pull request.

### Modified Capabilities
<!-- None: it reuses the agent and the tools as they are. Depends on `expose-passages-in-knowledge-tool` to edit existing documents. -->

## Impact

- New `src/ecosystem_assistant/pr_review/`, `evaluation/pr_review/`, `scripts/eval_pr_review.py`, tests, `docs/pr-review.md`. Tests use scripted models and never spend; a real-model run of the review set is optional and announced with an estimate.

## Non-goals

- A real webhook, a GitHub Action in a repository, or reading a PR from GitHub.
- Deciding by rules which PRs matter.
- Editing `service.yaml` or non-markdown files; changing the graph from a PR.
- Reviewing the quality of the documentation, or per-line coverage.
- Real repositories or data: only invented PRs (sending real code to an external model needs a decision first).

## Risk to note

The PR text is untrusted input to a model that can write documents. The prompt treats it as data and the tools write only markdown inside the workspace, but a hostile description could still push a misleading sentence into a document: hence `--dry-run` and the diffs in the report.
