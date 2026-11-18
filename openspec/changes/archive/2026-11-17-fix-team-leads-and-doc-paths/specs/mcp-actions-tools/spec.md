# Spec Delta

## ADDED Requirements

### Requirement: A workspace-relative path is rejected, not misread
A write tool SHALL reject a `doc_path` that starts with `repos/<service>/` for the given service, SHALL write nothing, and its error SHALL name the path inside the service to use.

#### Scenario: A citation path is rejected
- **GIVEN** the service `driver-service`
- **WHEN** `append_to_document` receives `repos/driver-service/README.md`
- **THEN** the call fails naming `README.md` and no file is created

#### Scenario: A path inside the service still works
- **GIVEN** the same service
- **WHEN** `append_to_document` receives `README.md`
- **THEN** the line is appended to the existing README
