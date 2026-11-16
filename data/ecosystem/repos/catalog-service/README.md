# catalog-service

Catalog service of Demo Grocery. It stores products, categories and prices, and exposes them through the `catalog-api` (REST, v1).

- **Owner:** catalog-team (tech lead: Nora Beltrán).
- **Stack:** a REST service with its own database. No dependencies on other services.
- **Events:** publishes `product.price_changed` every time a product's price changes.
- **Who uses it:** `orders-service` reads prices and stock to validate orders.

See `docs/api.md` for the endpoints and `docs/runbook-stale-prices.md` if prices look out of date.
