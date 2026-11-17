# Spec Delta

## ADDED Requirements

### Requirement: A documentation ticket can be created
The server SHALL offer `create_documentation_ticket(service, title, description, priority)`. It MUST write a markdown file `tickets/DOC-NNNN.md` at the workspace root, with the next free number, front matter holding the id, service, title, priority, status `open` and creation date, and the description as body; MUST return the id and path; MUST record the action in the audit log; and MUST NOT write inside `repos/`.

#### Scenario: A ticket is created with the next number
- **GIVEN** a workspace with no tickets
- **WHEN** the tool is called twice for an existing service
- **THEN** `tickets/DOC-0001.md` and `tickets/DOC-0002.md` exist with the given title, description and `status: open`
- **AND** the results carry the ids and the audit log has two entries

#### Scenario: Invalid input is refused and nothing is written
- **GIVEN** an unknown service, an empty title, a title with a line break, an empty description or an unknown priority
- **WHEN** the tool is called
- **THEN** an error that names the argument is returned and no ticket exists

#### Scenario: Two simultaneous creations never share a number
- **GIVEN** two calls made at the same time
- **WHEN** both finish
- **THEN** two files with different numbers exist

#### Scenario: Tickets are not part of the informational sources
- **GIVEN** a ticket was created
- **WHEN** the retrieval index is synced
- **THEN** the ticket is not indexed

#### Scenario: The tool has a correct schema
- **GIVEN** the real server
- **WHEN** its tools are listed
- **THEN** `create_documentation_ticket` has a description that says when not to use it and a closed schema with `service`, `title` and `description` required
