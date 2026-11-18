# Spec Delta

## ADDED Requirements

### Requirement: Missing data is written, not confirmed
The system prompt SHALL say that a fact the documentation does not mention is new and is written without asking; only a contradiction is asked about. The prompt MUST still name no MCP tool.

#### Scenario: The prompt separates a gap from a contradiction
- **GIVEN** the system prompt
- **WHEN** it is checked
- **THEN** it says that missing data is not a conflict and that it names no MCP tool
