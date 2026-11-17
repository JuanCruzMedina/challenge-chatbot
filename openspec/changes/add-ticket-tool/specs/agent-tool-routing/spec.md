# Spec Delta

## ADDED Requirements

### Requirement: A tool added to the server needs no change in the agent
The agent SHALL discover and run a tool added as a new module of the server's tools package without any change to the agent, chat, knowledge or model code.

#### Scenario: The agent runs the new ticket tool
- **GIVEN** the real server with the ticket module and a scripted model that asks for `create_documentation_ticket`
- **WHEN** the agent runs the turn
- **THEN** the tool runs, the ticket file exists and the reply reports it

#### Scenario: The agent source still names no tool
- **GIVEN** the real server's tool list including the ticket tool
- **WHEN** the agent source is searched for those names
- **THEN** none is found
