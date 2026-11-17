# Spec Delta

## ADDED Requirements

### Requirement: The planning catalog offers the listing queries
The flow's query catalog SHALL include `list_entities` and `team_overview`, so a plan can use them, and the planning prompt MUST describe them.

#### Scenario: A plan can request all teams
- **GIVEN** a scripted planner that returns `list_entities` with type `team`
- **WHEN** the question "which teams exist?" runs through the flow
- **THEN** the query executes against the graph and its result is cited as evidence
