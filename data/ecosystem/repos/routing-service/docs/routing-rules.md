# Routing rules

How `routing-service` assigns and recalculates routes.

## Assignment

- A delivery goes to the nearest available vehicle that can still arrive within its time window.
- A vehicle never carries more deliveries than its capacity.
- Every assignment publishes `route.assigned` with `vehicle_id`, the ordered stops and the expected arrival time of each stop.

## Recalculation

- A route is recalculated when a vehicle is more than 10 minutes behind its plan, based on the latest `vehicle.position_updated` events.
- Positions older than 30 seconds are ignored. If a vehicle has no fresh position, its route is kept and a warning is logged.
- A recalculation never removes a stop that the driver has already started.

## Limits

- Automatic assignment is the current priority (LOG-FEAT-102). Manual overrides by a dispatcher are not part of this version.
- Routing depends on `tracking-service`: if positions stop arriving, routes are not updated.
