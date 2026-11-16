# Product vision: Demo Logistics

Demo Logistics is a fictional fleet and delivery company. Its product goal for next year is **visibility and punctuality**: dispatchers must always know where every vehicle is, and drivers must receive routes that still make sense when the day goes differently from the plan.

## Principles

1. **Live visibility:** the position of a vehicle on the screen must be at most 30 seconds old. A stale position is worse than no position.
2. **Routes that hold up:** a route is assigned automatically from the positions of the fleet, and it is recalculated when a vehicle falls behind.
3. **Drivers first:** the driver sees one clear next step, never a list of problems. The driver application never blocks on a slow backend.

## Epics

- **LOG-EPIC-01 Live fleet visibility:** vehicle positions for dispatchers and for the driver application.
- **LOG-EPIC-02 Reliable routes:** automatic route assignment and driver notifications.

## Current priority

The priority of the quarter is **LOG-FEAT-102 (automatic route assignment)**, because manual assignment is the main reason for late deliveries. It depends on `tracking-service` publishing fresh positions and on `driver-service` delivering the route to the driver in seconds.

This client does not process payments and does not sell anything to end customers: its users are dispatchers and drivers. Product owner: Camila Ortega.
