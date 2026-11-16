# payments-service

Payments service of Demo Grocery. It charges cards through an external (fictional) payment provider, handles refunds and publishes the result of each charge.

- **Owner:** payments-team (tech lead: Valeria Sosa).
- **API:** `payments-api` v2 (active, with automatic retries) and v1 (**deprecated**, sunset 2027-03-31). See `docs/api-v2.md` and `docs/api-v1.md`.
- **Events it publishes:** `payment.confirmed`, `payment.failed`.
- **Events it consumes:** `order.created`.
- **Who uses it:** `orders-service` requests charges. It still uses v1 and must migrate to v2.

If charges fail or are slow, see `docs/runbook-failed-payments.md`.
