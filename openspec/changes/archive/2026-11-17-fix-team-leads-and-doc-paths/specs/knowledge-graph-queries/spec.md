# Spec Delta

## ADDED Requirements

### Requirement: One query gives every team with its services and leads
The graph SHALL answer `teams_overview` with every team, the services each owns and the lead of each service, and the plan catalog SHALL offer it without arguments.

#### Scenario: Every team comes with its leads
- **GIVEN** the committed sample data
- **WHEN** `teams_overview` runs
- **THEN** seven teams are returned and each service shows its lead, for example `orders-service` led by Tomás Aguirre

#### Scenario: The catalog offers it without arguments
- **GIVEN** the plan catalog
- **WHEN** a plan asks for `teams_overview` with no arguments
- **THEN** the plan keeps the query
