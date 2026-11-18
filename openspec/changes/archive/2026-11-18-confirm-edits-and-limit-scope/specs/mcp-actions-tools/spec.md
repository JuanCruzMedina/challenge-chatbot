# Spec Delta

## ADDED Requirements

### Requirement: Edits and obsolete marks show a preview and wait for confirmation
`update_document` and `mark_document_obsolete` SHALL, unless `confirmed` is true, write nothing and return outcome `needs_confirmation` with a diff of the change. With `confirmed: true` they SHALL write. Creating and appending MUST stay direct. A conflict MUST be reported before any preview. The server MUST ask for confirmation unless `ACTIONS_CONFIRM_EDITS` is `off`.

#### Scenario: An unconfirmed edit is only previewed
- **GIVEN** a server that asks for confirmation
- **WHEN** `update_document` runs without `confirmed`
- **THEN** the result is `needs_confirmation` with a diff, the file is unchanged and the audit log is empty

#### Scenario: A confirmed edit is written
- **GIVEN** the same call with `confirmed: true`
- **WHEN** it runs
- **THEN** the file has the new text and the audit log has one entry

#### Scenario: Obsolete marks are previewed too
- **GIVEN** a server that asks for confirmation
- **WHEN** `mark_document_obsolete` runs without `confirmed`
- **THEN** nothing is written and the preview shows the front matter to be added

#### Scenario: Creating and appending are not asked
- **GIVEN** a server that asks for confirmation
- **WHEN** `add_document` or `append_to_document` runs
- **THEN** the document is written at once

#### Scenario: A conflict comes before the preview
- **GIVEN** an edit whose old text is not in the document
- **WHEN** it runs unconfirmed
- **THEN** the result is `conflict`

### Requirement: A session can be limited to some services
The server SHALL read `ACTIONS_ALLOWED_SERVICES` and reject any write to another service with an error that names the allowed services, writing nothing. When it is unset every service is allowed.

#### Scenario: A write outside the scope is rejected
- **GIVEN** a server limited to `payments-service`
- **WHEN** a document of `notifications-service` is created
- **THEN** the call fails naming `payments-service` and no file is created

#### Scenario: A write inside the scope works
- **GIVEN** the same server
- **WHEN** a document of `payments-service` is created
- **THEN** it is written
