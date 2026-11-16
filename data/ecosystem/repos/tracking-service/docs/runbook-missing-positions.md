# Runbook: a vehicle disappears from the map

**Symptom:** a dispatcher cannot see a vehicle, or its position is marked `stale`.

## Diagnosis

1. Query `GET /vehicles/{id}/position` and read `received_at`. If it is recent, the problem is in the dashboard, not here.
2. If the position is old, check whether the vehicle's device is still sending. No positions in the last 5 minutes usually means a device or network problem.
3. If many vehicles are stale at once, check the ingestion queue of `tracking-service`: a growing queue means a processing delay.

## Fix

- One vehicle: ask the driver to restart the device, and confirm that a new position arrives.
- Many vehicles: restart the position consumers and verify that `vehicle.position_updated` events flow again. Tell `routing-service`'s owners, because routes depend on fresh positions.

**Escalation:** tracking-team, on call 24x7 during delivery hours.
