# Spec Delta

## ADDED Requirements

### Requirement: A new document can say what it is about
`add_document` SHALL accept `about`, a list of names, and write the names that match a service of the workspace or an API or event declared by a service manifest into the front matter of the new document. Names that match nothing MUST NOT be written and MUST be listed as `unresolved` in the result. Without `about` the document is written as before.

#### Scenario: Known names are written
- **GIVEN** a workspace with `payments-service` and `payments-api`
- **WHEN** a document is added with `about: [payments-service, payments-api]`
- **THEN** its front matter has both names and the result lists no unresolved name

#### Scenario: Unknown names are dropped and reported
- **GIVEN** the same workspace
- **WHEN** a document is added with `about: [payments-api, ghost-service]`
- **THEN** only `payments-api` is written and the result lists `ghost-service` as unresolved

#### Scenario: A document with its own front matter keeps it
- **GIVEN** content that starts with front matter
- **WHEN** it is added with `about`
- **THEN** the front matter has its own fields and the `about` field

#### Scenario: Without about nothing changes
- **GIVEN** a call without `about`
- **WHEN** the document is added
- **THEN** the file is exactly the content given

### Requirement: The links of an existing document can be set
The server SHALL offer `link_document`, which replaces the `about` list of an existing document with the names that match the workspace, removes it when the list is empty, reports unresolved names, returns the previous list and writes one audit entry. It MUST NOT change the body or other front matter fields.

#### Scenario: Links are replaced and the previous ones returned
- **GIVEN** a document about `payments-service`
- **WHEN** `link_document` sets `[payments-api]`
- **THEN** the front matter has only `payments-api`, the result returns `payments-service` as the previous list and the body is unchanged

#### Scenario: An empty list removes the field
- **GIVEN** a document with `about`
- **WHEN** `link_document` sets an empty list
- **THEN** the field is gone and the rest of the file is unchanged

#### Scenario: A multi-line list written by hand is replaced
- **GIVEN** a document whose `about` is a multi-line YAML list
- **WHEN** `link_document` sets new names
- **THEN** the old items are gone and no other field is touched

#### Scenario: The tool follows the rules of the other write tools
- **GIVEN** a server limited to another service
- **WHEN** `link_document` targets a service outside the scope
- **THEN** it fails and nothing is written

#### Scenario: The new tool is discovered with a closed schema
- **GIVEN** the real server
- **WHEN** its tools are listed
- **THEN** `link_document` is there with `service`, `doc_path` and `about` required and unknown arguments rejected
