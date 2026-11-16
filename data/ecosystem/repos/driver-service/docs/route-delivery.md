# Route delivery to drivers

How `driver-service` gets a route to the driver.

## Flow

1. `routing-service` publishes `route.assigned` with the vehicle, the ordered stops and the expected arrival times.
2. `driver-service` stores the route and pushes a notification to the driver application of that vehicle.
3. The application shows one clear next step. When the driver completes a stop, the application confirms it and `driver-service` marks it done.

## Rules

- The application must show the route within 5 seconds of the event. If the push fails, the route is delivered the next time the application opens.
- A route that is replaced while the driver is on a stop keeps that stop first (the driver never loses a stop already started).
- The driver sees the position of their own vehicle through `tracking-api`. If the position is stale, the application hides it instead of showing a wrong one.

## Status

Driver route notifications (LOG-FEAT-201) are planned and not released yet: today the route appears when the application is opened.
