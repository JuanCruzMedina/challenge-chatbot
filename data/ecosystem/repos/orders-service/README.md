# orders-service

Orders service of Demo Grocery. It receives the purchase, validates prices and stock against `catalog-api`, asks `payments-api` for the charge and keeps the order state.

- **Owner:** orders-team (tech lead: Tomás Aguirre).
- **Order states:** `CREATED`, `PAYMENT_PENDING`, `PAID`, `CANCELLED`.
- **Depends on:** `catalog-service` (prices and stock) and `payments-service` (charges).
- **Events it publishes:** `order.created`, `order.cancelled`.
- **Events it consumes:** `payment.confirmed`, `payment.failed`, `product.price_changed`.

Design decisions are in `docs/adr-001-event-driven-orders.md`. For orders that do not move forward, see `docs/runbook-stuck-order.md`.
