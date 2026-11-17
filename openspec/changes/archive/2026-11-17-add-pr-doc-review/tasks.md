# Tasks

## 1. Reading a pull request
- [x] 1.1 Write failing tests for the two input scenarios; implement the loader (`pr_review/pull_request.py`) and the review message builder.

## 2. The review
- [x] 2.1 Write failing tests for the three decision scenarios with a scripted chat, the real MCP server and a copy of the sample data; implement `review_pull_request`.
- [x] 2.2 Write the failing test for the report (diffs, tool calls, "no change" derived from files); implement it.
- [x] 2.3 Write the isolation test (no string inspection of the pull request text, no server tool names, no import of the actions package) and mutation-check it.

## 3. Dry run and command
- [x] 3.1 Write failing tests for dry run (the real workspace is byte-identical, no leftover process) and for the exit codes; implement the command and `--dry-run`.

## 4. The review set
- [x] 4.1 Write the six invented pull requests and the grading in `scripts/eval_pr_review.py` with failing tests for the grading scenario; implement.

## 5. Documentation and closing
- [x] 5.1 Write `docs/pr-review.md` (how it works, a worked example run by a test, the CI example that is not installed, the risk of untrusted PR text, what was measured) and update the roadmap.
- [x] 5.2 Run the suite, the data validator and `OPENSPEC_TELEMETRY=0 openspec validate add-pr-doc-review --strict`; map scenarios to tests.
- [ ] 5.3 (Optional, needs the user's yes and an announced estimate) Run the review set with the real model and report the rate by kind with its limits.
