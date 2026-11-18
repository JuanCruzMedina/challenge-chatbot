# Spec Delta

## ADDED Requirements

### Requirement: The agent says what a new document is about
The system prompt SHALL tell the model that, when it creates a document, it says what the document is about with names it knows from the conversation or the knowledge tool and never invents them; that when it cannot tell it asks one question with the likely options; and that afterwards it says which links were added or left out. The prompt MUST still name no MCP tool.

#### Scenario: The prompt has the rule and names no tool
- **GIVEN** the system prompt
- **WHEN** it is checked
- **THEN** it has the rule, is under 40 lines and names no MCP tool

#### Scenario: A scripted turn creates a document with links and corrects one
- **GIVEN** a scripted model that creates a document with one known and one unknown name, then fixes the links
- **WHEN** the turns run on the real server
- **THEN** the first result reports the unknown name and the final file has only the right links
