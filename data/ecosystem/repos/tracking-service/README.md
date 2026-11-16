# tracking-service

Tracking service of Demo Logistics. It receives the GPS positions that vehicles send, keeps the latest position of each vehicle and publishes every update.

- **Owner:** tracking-team (tech lead: Bruno Salas). Application: Fleet Tracker.
- **API:** `tracking-api` v1 (REST, read-only). See `docs/api.md`.
- **Events it publishes:** `vehicle.position_updated`.
- **Who uses it:** `routing-service` listens to the position events to plan routes, and `driver-service` reads positions through the API.

If a vehicle disappears from the map, see `docs/runbook-missing-positions.md`.
