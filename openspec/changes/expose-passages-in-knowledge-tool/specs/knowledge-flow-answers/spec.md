# Spec Delta

## ADDED Requirements

### Requirement: The answer exposes the document passages it retrieved
The flow's answer SHALL carry the document passages it retrieved, each with its path, heading path and text, and MUST mark a passage that was cut or whose text is not exactly as in the file.

#### Scenario: Passages come with the answer
- **GIVEN** a question that retrieves two document passages
- **WHEN** the flow answers
- **THEN** the answer lists both with path, heading path and text

#### Scenario: A passage is an exact piece of its file
- **GIVEN** every markdown document of the sample data
- **WHEN** its passages are produced
- **THEN** the text of each exact passage appears in the file exactly as written

#### Scenario: A long passage is marked as cut
- **GIVEN** a section longer than 1,500 characters
- **WHEN** its passage is exposed
- **THEN** it is cut and marked truncated
