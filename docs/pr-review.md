# Reviewing documentation when a pull request is merged

When a pull request is merged, the documentation of the service may now be wrong, or may never have covered the new
behavior. The review gives the pull request to **the same agent** as the chat and lets it decide, with its own tools:
check what the documentation says, add a document, update a passage, or change nothing. **No code in the package
decides what a pull request needs.** A test checks that the package has no string inspection of the pull request text,
does not import the actions code and names no tool of the server.

The review is made for a business view: what the service now does or promises differently, who is affected, what a
reader would be misled about. It is told that refactors, renames, formatting, tests, dependency bumps, typo fixes and
internal details do not deserve documentation, and that "change nothing" is a good answer.

## How to run it

```
uv run python -m ecosystem_assistant.pr_review path/to/pr.yaml             # review and write
uv run python -m ecosystem_assistant.pr_review path/to/pr.yaml --dry-run   # work on a copy, only report
```

The workspace is `AGENT_DATA_ROOT` (default `var/workspace`, created with `scripts/seed_workspace.py`); `--workspace`
chooses another. The model is chosen by `LLM_PROVIDER` as everywhere else (with `anthropic` the spending cap of the
ledger applies). Exit code 0 after a review; 2 when the pull request file is invalid, the workspace is missing or the
model cannot be used (the message says what to do).

## The pull request file

The format of `data/ecosystem/prs/*/pr.yaml`, with an optional `patch` text per change:

```yaml
id: PR-202
repo: demo-grocery/payments-service      # the service is the last part
title: "Automatic retries for payments-api v1"
description: >
  payments-api v1 now retries a failed charge automatically, up to 3 times.
changes:
  - {path: src/charges.py, status: modified, patch: "+MAX_RETRIES = 3"}
```

A missing field is reported by name. Patches longer than 4,000 characters (12,000 in total) are cut and marked as cut.
The title and the description carry the business view, so the patches can be left out.

## The report

Built by code from what happened, not from what the model says it did:

- **Decision**: `changed` when at least one markdown file differs after the run, `no_change` otherwise.
- **Tool calls**: every call except the knowledge tool, with arguments, result and a status: `ok`, `conflict` (the tool said the text to replace was not found or not unique, so nothing was written) or `failed` (the tool reported an error). The text report shows the status and counts the calls that wrote nothing, so the model's explanation can be compared with the diffs: a model may say it changed something that a conflict stopped.
- **Diffs**: a unified diff for every markdown file that changed or was created.
- **Explanation**: the model's last message, shown as its own words.

With `--dry-run` the agent works on a copy of the workspace that is deleted afterwards, so the report is a proposal and
nothing real (documents, audit log, index of the project) changes.

## Example

The example runs in a test with scripted models: the review, the agent, the real MCP server and the real knowledge flow
are used as they are; only the decisions of the models are scripted. (The scripted knowledge flow reads the original
sample data; the real command points the flow at the workspace it reviews.)

```python
import asyncio, shutil, tempfile
from pathlib import Path
from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.knowledge import KnowledgeService
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import ScriptedLLM
from ecosystem_assistant.pr_review import Change, PullRequest, review_pull_request

work = Path(tempfile.mkdtemp())
shutil.copytree("data/ecosystem", work / "workspace")
flow_model = ScriptedLLM([
    {"graph_queries": []},
    {"answer": "The rules say v1 has no automatic retries [D1].", "citations": ["D1"]},
])
knowledge = KnowledgeService(work / "workspace", RetrievalIndex(work / "index", HashingEmbedder()), flow_model, min_score=0.0)
old = "v1 does **not** support automatic retries: after a failure, the consumer must create a new charge."
chat = ScriptedChat(script=[
    ai_tool("query_knowledge", {"question": "Does payments api v1 support automatic retries?"}, "a"),
    ai_tool("update_document", {"service": "payments-service", "doc_path": "docs/api-v1.md", "old_text": old,
                                "new_text": "v1 retries a failed charge up to 3 times automatically."}, "b"),
    ai_text("The v1 rule said there were no automatic retries; the PR adds them, so I updated that rule."),
])
pr = PullRequest("PR-202", "demo-grocery/payments-service", "Automatic retries for payments-api v1",
                 "payments-api v1 now retries a failed charge up to 3 times.", [Change("src/charges.py", "modified")])

def open_agent(workspace, audit, scratch, server_env):
    return Agent.open(chat=chat, workspace=workspace, audit_file=work / "audit.jsonl", knowledge=knowledge,
                      extra_env=server_env)

report = asyncio.run(review_pull_request(pr, work / "workspace", open_agent, dry_run=True))
print(report.render())
```

```text
PR-202: documentation changed (dry run: nothing was written for real)
  - update_document

--- a/repos/payments-service/docs/api-v1.md
+++ b/repos/payments-service/docs/api-v1.md
@@ -16,5 +16,5 @@
 
 - Amounts in cents with an ISO currency.
 - `Idempotency-Key` is mandatory on `POST /payments`.
-- v1 does **not** support automatic retries: after a failure, the consumer must create a new charge.
+- v1 retries a failed charge up to 3 times automatically.
 - External provider timeout: 20 seconds. After that the charge is marked `FAILED`.

Model's explanation: The v1 rule said there were no automatic retries; the PR adds them, so I updated that rule.
```

## Measured with

The behavior of the code (reading, message, decisions given a scripted model, report, dry run, exit codes, grading) is
tested. How well a real model decides was measured on a small set: with Claude Haiku 5.5 it passed **5/6 or 6/6** depending on the run (the case that updates an existing document passed 4 of 5 times alone). `evaluation/pr_review.yaml` has six invented pull
requests (a new behavior with no document, a changed behavior with a document, and four that deserve nothing: a
refactor, tests only, a typo, a dependency bump) and `scripts/eval_pr_review.py` grades them by the effect on the
files, with no judge model:

```
LLM_PROVIDER=anthropic uv run python scripts/eval_pr_review.py --min-rate 0.7
```

## In CI

An example of a job that reviews the merged pull request and commits the changed documents. **It is not installed
anywhere**; it is here so the shape is clear.

```yaml
# .github/workflows/docs-review.yml  (example only)
on:
  pull_request:
    types: [closed]
jobs:
  review-docs:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./scripts/export_pr.sh "${{ github.event.pull_request.number }}" > pr.yaml   # a script you write: PR to pr.yaml
      - run: uv run python -m ecosystem_assistant.pr_review pr.yaml --workspace ./docs-workspace
      - run: git add -A && git commit -m "docs: review for PR ${{ github.event.pull_request.number }}" && git push
```

## Limits

- **The pull request text is untrusted input to a model that can write documents.** The prompt tells the model to
  treat it as data and the tools can only write markdown inside the workspace, but a hostile description could still
  push a misleading sentence into a document **of the PR's own service**. Use `--dry-run` and read the diffs when the source is not trusted.
- **A review cannot leave the PR's service.** The review starts the actions server with `ACTIONS_ALLOWED_SERVICES` set to the service of the PR and `ACTIONS_CONFIRM_EDITS=off`. The server enforces the limit, so a description that asks to change another service's documents is rejected whatever the model does (`test_a_write_to_another_service_is_rejected_whatever_the_pr_text_says`). Confirmation is off because the report and `--dry-run` are the safeguard of a review.
- Real pull requests and real repositories are out of scope (invented data only). Sending real code to an external
  model needs a decision about privacy first.
- Fetching the pull request from GitHub, and committing or opening a pull request with the result, are not built.
- `service.yaml` and other non-markdown files are never edited, and the graph does not learn from a pull request.
- A new document is searchable at the next question (the agent refreshes the index), but it appears in the graph only
  when a manifest lists it (see [roadmap.md](roadmap.md)).
- The model sees only the part of the diff that fits, and the quality of its decision depends on it.
