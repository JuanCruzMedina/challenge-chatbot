# driver-service

Backend of the Driver App of Demo Logistics. Drivers use it on the road to see their next stop and to confirm deliveries.

- **Owner:** driver-team (tech lead: Diego Núñez). Application: Driver App.
- **Events it consumes:** `route.assigned`, published by `routing-service`.
- **APIs it consumes:** `tracking-api`, to show a driver the latest position of their own vehicle.
- **It provides no API to other services.** Only the mobile application talks to it.

How a route reaches a driver is described in `docs/route-delivery.md`.
