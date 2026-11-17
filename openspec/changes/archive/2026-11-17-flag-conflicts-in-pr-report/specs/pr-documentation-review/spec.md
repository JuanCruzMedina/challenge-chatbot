# Spec Delta

## ADDED Requirements

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
