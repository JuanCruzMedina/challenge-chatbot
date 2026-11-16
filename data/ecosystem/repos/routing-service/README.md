# routing-service

Routing service of Demo Logistics. It decides which vehicle takes which delivery and in which order, and it recalculates when a vehicle falls behind.

- **Owner:** routing-team (tech lead: Elena Pardo). Application: Fleet Tracker.
- **Events it consumes:** `vehicle.position_updated`.
- **Events it publishes:** `route.assigned`, one per vehicle whenever its route is created or changed.
- **API:** none. Other services react to its events.

The planning rules and their limits are in `docs/routing-rules.md`.
