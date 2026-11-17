# Spec Delta

## ADDED Requirements

### Requirement: Entities of a type can be listed
The graph SHALL offer `list_entities(type)` returning every entity of that type, sorted by name, with its sources. An unknown type MUST return the list of valid types.

#### Scenario: All teams are listed
- **GIVEN** the sample ecosystem
- **WHEN** `list_entities("team")` runs
- **THEN** `orders-team`, `driver-team` and the other teams of the data are returned

#### Scenario: An unknown type names the valid ones
- **GIVEN** the sample ecosystem
- **WHEN** `list_entities("planet")` runs
- **THEN** a not-found result lists the valid types

### Requirement: A team can be shown with its services and leads
The graph SHALL offer `team_overview(team)` returning the services the team owns and the person leading each.

#### Scenario: A team with its services and leads
- **GIVEN** the sample ecosystem
- **WHEN** `team_overview("orders-team")` runs
- **THEN** `orders-service` is returned with `Tomás Aguirre` as its lead

#### Scenario: An unknown team is not found
- **GIVEN** the sample ecosystem
- **WHEN** `team_overview("ghost-team")` runs
- **THEN** a not-found result is returned
