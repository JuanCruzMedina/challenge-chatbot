# Runbook: stale prices in the catalog

**Symptom:** a customer sees a price different from the one the commercial team loaded.

## Diagnosis

1. Query `GET /products/{id}` directly on `catalog-service` and compare it with what the order shows.
2. Check whether the `product.price_changed` event was published. If it was not, the problem is in the price load.
3. If the event was published but `orders-service` shows another value, the problem is the order price cache (see the stuck-order runbook).

## Fix

- If the load failed: retry the update from the commercial panel and confirm the event.
- If the `orders-service` cache is old: invalidate it and notify orders-team.

**Escalation:** catalog-team, on call Monday to Friday, 9 to 18.
