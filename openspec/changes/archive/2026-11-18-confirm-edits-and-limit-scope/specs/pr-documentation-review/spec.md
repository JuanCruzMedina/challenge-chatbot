# Spec Delta

## ADDED Requirements

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
