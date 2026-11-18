# pr-documentation-review Specification

## Purpose
Defines the review of a merged pull request: whether documentation about its behavior exists, and adding, updating or leaving it.

## Requirements

### Requirement: A pull request is read from a file
The review SHALL read a pull request from a YAML file with an id, a repo, a title, a description and a list of changes with path, status and an optional patch, and MUST report the invalid field by name when the file is not valid.

#### Scenario: A valid pull request is read
- **GIVEN** the sample `pr.yaml`
- **WHEN** it is loaded
- **THEN** the id, service, title, description and changed paths are available

#### Scenario: An invalid file names the problem
- **GIVEN** a pull request file without a title or with a change that has no path
- **WHEN** it is loaded
- **THEN** an error names the missing field

### Requirement: The agent decides what the documentation needs
The review SHALL give the pull request to the agent with instructions to think at business and key-logic level, to check existing documentation with the knowledge tool, to add a document only when none covers the behavior, to update only when the existing text would be wrong or incomplete, and to do nothing for changes that do not warrant it. No code in the package MAY decide that by inspecting the pull request text.

#### Scenario: A new behavior with no document gets one
- **GIVEN** a pull request about a behavior no document covers and a scripted model that adds a document
- **WHEN** the review runs
- **THEN** the document exists with the scripted text and the report lists the creation

#### Scenario: A changed behavior updates its document
- **GIVEN** a pull request that makes an existing passage wrong and a scripted model that quotes it and replaces it
- **WHEN** the review runs
- **THEN** the file has the new text and the old text is gone

#### Scenario: A change that does not warrant documentation changes nothing
- **GIVEN** a refactor pull request and a scripted model that calls no write tool
- **WHEN** the review runs
- **THEN** the workspace is untouched and the report says no change with the model's explanation

#### Scenario: The package has no rule of its own
- **GIVEN** the source of the package
- **WHEN** it is checked for string inspection of the pull request text and for tool names of the server
- **THEN** none is found

### Requirement: The report is built from what happened
The review SHALL return a report with the tool calls other than the knowledge tool, a unified diff for each changed markdown file and the model's explanation, and MUST derive "no change" from the absence of a changed file.

#### Scenario: The report shows tool calls and diffs
- **GIVEN** a review that updated one document
- **WHEN** the report is produced
- **THEN** it lists that tool call and a diff with the removed and the added lines

### Requirement: A dry run changes nothing
With `--dry-run` the review SHALL run on a copy of the workspace, report as usual and leave the real workspace and audit log untouched.

#### Scenario: Dry run leaves no trace
- **GIVEN** a review that would create a document
- **WHEN** it runs with `--dry-run`
- **THEN** the report shows the creation and the real workspace is byte for byte the same

### Requirement: The command is usable from CI
The command SHALL exit 0 after a review, exit 2 with a message when the model or the workspace cannot be used, and leave no MCP server process behind.

#### Scenario: Exit codes
- **GIVEN** a workspace that does not exist
- **WHEN** the command runs
- **THEN** it exits with code 2 and prints how to create the workspace

### Requirement: The review set measures the behavior without a judge model
`evaluation/pr_review/` SHALL hold invented pull requests of the kinds above and `scripts/eval_pr_review.py` SHALL grade each by the effect on files, reporting a pass rate by kind.

#### Scenario: Grading follows the files
- **GIVEN** scripted reviews that do the right and the wrong thing for each kind
- **WHEN** the script grades them
- **THEN** right ones pass, wrong ones fail with the reason, and the report groups by kind

### Requirement: The report marks the calls that did not write
The report SHALL give each tool call a status: `failed` when the tool returned an error, `conflict` when the result's outcome is `conflict`, and `ok` otherwise; and MUST show how many calls did not write anything next to the decision.

#### Scenario: A conflict is marked and nothing is claimed as written
- **GIVEN** a review whose only write call quotes text that is not in the document
- **WHEN** the report is produced
- **THEN** the call has the status `conflict`, the decision is `no_change` and the text report says one call wrote nothing

#### Scenario: A successful call is ok and a failing call is failed
- **GIVEN** a review with a successful write and a write to a service that does not exist
- **WHEN** the report is produced
- **THEN** the statuses are `ok` and `failed`

### Requirement: A review can only change the documents of the PR's service
A review SHALL start the actions server limited to the service of the pull request and without confirmation of edits, so the limit holds whatever the PR text says.

#### Scenario: The review passes the limit to the server
- **GIVEN** a PR of `payments-service`
- **WHEN** the review opens the agent
- **THEN** the server environment limits writes to `payments-service` and turns confirmation off

#### Scenario: A write to another service is rejected
- **GIVEN** a review of a PR of `payments-service` in which the model tries to create a document of another service
- **WHEN** the review runs
- **THEN** that call fails, no file is created and the decision is "no change"

#### Scenario: An edit of the PR's own service is applied without confirmation
- **GIVEN** a review in which the model edits a document of the PR's service
- **WHEN** the review runs
- **THEN** the edit is written in that same run
