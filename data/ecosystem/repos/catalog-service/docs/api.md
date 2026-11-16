# catalog-api v1

A read-only REST API for internal consumers.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/products/{id}` | Returns a product with its current price and stock. |
| GET | `/products?category=` | Lists the products of a category (paged, 50 per page). |
| GET | `/categories` | Lists the active categories. |

## Rules

- Prices are reported in cents (integer) with an ISO currency (`ARS`, `USD`).
- Every price change publishes the `product.price_changed` event with `product_id`, `old_price` and `new_price`.
- Limit of 200 requests per minute per consumer. Going over it returns `429`.
- A product with no stock is still returned, with `stock: 0`. The consumer decides what to do.
