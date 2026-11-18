# Spec Delta

## ADDED Requirements

### Requirement: The reply is rendered and the notes are dimmed
The terminal chat SHALL print the agent's reply rendered as markdown, the line of called tools and the greeting dimmed, and failures in red. It MUST hand the reply to the renderer as it is, without inspecting or changing its text, and MUST print plain text when the output is not a terminal.

#### Scenario: A markdown table is rendered
- **GIVEN** a reply with a markdown table and bold text
- **WHEN** it is printed to a terminal
- **THEN** the table is drawn as a table and the bold markers are not shown

#### Scenario: The tools line is dimmed and the error is red
- **GIVEN** a turn that called a tool and a turn that failed
- **WHEN** they are printed to a terminal
- **THEN** the tools line has the dim style and the error line has the red style

#### Scenario: A pipe gets plain text
- **GIVEN** the output is not a terminal
- **WHEN** a reply is printed
- **THEN** no escape sequences are written

#### Scenario: The loop uses the given outputs
- **GIVEN** a loop with its own reply, note and error outputs
- **WHEN** a turn runs
- **THEN** the reply goes to the reply output, the tools line to the note output and a failure to the error output
