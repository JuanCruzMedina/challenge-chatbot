# Spec Delta

## ADDED Requirements

### Requirement: A passage says which service and path it belongs to
Each passage of an answer SHALL carry `service` and `doc_path`, the path inside the service, when the document belongs to a service.

#### Scenario: A service document names its service and inner path
- **GIVEN** a passage of `repos/driver-service/README.md`
- **WHEN** the answer lists it
- **THEN** its service is `driver-service` and its doc_path is `README.md`

#### Scenario: A document outside a service has no service
- **GIVEN** a passage of a client's product vision
- **WHEN** the answer lists it
- **THEN** its service and doc_path are empty
