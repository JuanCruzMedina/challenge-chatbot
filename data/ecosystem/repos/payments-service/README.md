# payments-service

Payments service of Demo Grocery. It charges cards through an external (fictional) payment provider, handles refunds and publishes the result of each charge.

- **Owner:** payments-team (tech lead: Valeria Sosa).
- **API:** `payments-api` v1 (REST). See `docs/api-v1.md`.
- **Events it publishes:** `payment.confirmed`, `payment.failed`.
- **Events it consumes:** `order.created`.
- **Who uses it:** `orders-service` requests charges with `POST /payments`.

If charges fail or are slow, see `docs/runbook-failed-payments.md`.
