# Spec Delta

## ADDED Requirements

### Requirement: The prompt tells the model to act on confirmations and to check conflicts
The system prompt SHALL state that a confirmation from the person is the order to act and that asking again is only for a value a tool requires and is unknown; that a fact the person gives about owners, leads or other documented data is checked with the knowledge tool before writing and the person is asked only when it contradicts the documentation; and that write tools handle markdown documents only. It MUST name no MCP tool.

#### Scenario: The prompt carries the rules and names no tool
- **GIVEN** the system prompt and the real server's tool list
- **WHEN** the prompt is checked
- **THEN** it contains the confirmation, conflict and markdown-only rules
- **AND** no MCP tool name appears in it

#### Scenario: After a confirmation the scripted model writes in the same turn
- **GIVEN** a conversation where the person has confirmed a proposal, and a scripted model that calls `append_to_document`
- **WHEN** the turn runs
- **THEN** the tool runs once, the file has the text and the reply reports it
