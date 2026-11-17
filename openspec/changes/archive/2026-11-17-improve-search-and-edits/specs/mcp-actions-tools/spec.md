# Spec Delta

## ADDED Requirements

### Requirement: Text can be appended to a document without quoting it
The server SHALL offer `append_to_document(service, doc_path, text)`. It MUST add the text at the end of an existing markdown document, or create the document when it does not exist, using the same path rules as the other tools, and MUST record the action in the audit log.

#### Scenario: Appending to an existing document
- **GIVEN** `docs/lead.md` exists in a service
- **WHEN** the tool is called with new text
- **THEN** the original content is unchanged and the new text follows it
- **AND** the outcome is `appended` and the audit log has one entry

#### Scenario: Appending to a missing document creates it
- **GIVEN** `docs/team.md` does not exist
- **WHEN** the tool is called
- **THEN** the file is created with the text and the outcome is `created`

#### Scenario: Invalid input is refused and nothing is written
- **GIVEN** an unknown service, a path outside the service, a non-markdown path or empty text
- **WHEN** the tool is called
- **THEN** an error is returned and no file changes

#### Scenario: The agent discovers the tool without being changed
- **GIVEN** the real server
- **WHEN** the agent lists its tools
- **THEN** `append_to_document` is present and its name appears nowhere in the agent source
