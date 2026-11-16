# tracking-api v1

A read-only REST API for internal consumers.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/vehicles/{id}/position` | Latest known position of a vehicle, with the time it was received. |
| GET | `/vehicles?status=` | Lists vehicles, optionally filtered by `active` or `idle`. |

## Rules

- A position is a latitude, a longitude and a `received_at` timestamp in UTC.
- Positions older than 30 seconds are returned with `stale: true`. The consumer decides what to show.
- Every accepted position publishes `vehicle.position_updated` with `vehicle_id`, `lat`, `lon` and `received_at`.
- Limit of 300 requests per minute per consumer. Going over it returns `429`.
