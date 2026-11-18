# Spec Delta

## ADDED Requirements

### Requirement: A cut graph answer is marked, and no catalog query is cut on the sample data
A graph answer longer than the cap SHALL be marked as truncated and the flow's trace SHALL record it. Every query of the catalog, run on the sample data, MUST fit under the cap.

#### Scenario: Every catalog query fits
- **GIVEN** the sample data and a representative argument for each catalog query
- **WHEN** each query runs as the flow runs it
- **THEN** no answer is marked truncated

#### Scenario: A new query without a case fails the guard
- **GIVEN** the catalog
- **WHEN** a query exists that the guard has no case for
- **THEN** the guard test fails naming it

#### Scenario: A cut answer is marked and traced
- **GIVEN** a query whose answer is longer than a small cap
- **WHEN** it runs
- **THEN** the fact is marked truncated and the trace step lists it as truncated
