# Spec Delta

## ADDED Requirements

### Requirement: A preview is shown and confirmed before it is repeated
The system prompt SHALL tell the model that when a tool returns a preview that needs confirmation it must show it to the person and wait, and repeat the call as the tool says only after the person agrees. The prompt MUST still name no MCP tool.

#### Scenario: The prompt has the preview rule
- **GIVEN** the system prompt
- **WHEN** it is checked
- **THEN** it has the preview rule and names no MCP tool

#### Scenario: A scripted turn previews, waits and then writes
- **GIVEN** a scripted model that asks for an edit, shows the preview and, after a "yes", repeats the call confirmed
- **WHEN** the two turns run on the real server
- **THEN** the file changes only in the second turn
