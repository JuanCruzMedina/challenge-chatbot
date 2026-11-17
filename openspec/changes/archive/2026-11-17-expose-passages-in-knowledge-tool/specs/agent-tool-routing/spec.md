# Spec Delta

## ADDED Requirements

### Requirement: The knowledge tool returns passages that can be quoted for an edit
The `query_knowledge` result SHALL include the passages of the answer, and the system prompt SHALL tell the model to quote the text to replace from them when changing an existing document, to ask again for the section when it is not among them, and never to invent it. The prompt MUST still name no MCP tool.

#### Scenario: The tool result includes the passages
- **GIVEN** a question answered with document evidence
- **WHEN** the agent runs `query_knowledge`
- **THEN** the tool message has a `passages` list with exact text

#### Scenario: A scripted turn edits a document using a quoted passage
- **GIVEN** a scripted model that asks the knowledge tool for a section and then calls the update tool with text copied from a returned passage
- **WHEN** the turn runs
- **THEN** the update succeeds and the file has the new text

#### Scenario: The prompt carries the rule and names no tool
- **GIVEN** the system prompt and the real server's tool list
- **WHEN** the prompt is checked
- **THEN** it has the quoting rule and no MCP tool name appears in it
