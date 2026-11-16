# orders-api v1

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/orders` | Creates an order. Validates price and stock with `catalog-api` and publishes `order.created`. |
| GET | `/orders/{id}` | Returns the order and its current state. |
| POST | `/orders/{id}/cancel` | Cancels an order that is not paid yet and publishes `order.cancelled`. |

## Charges

When an order is created, `orders-service` requests the charge by calling `payments-api` v1 (`POST /payments`). The result arrives asynchronously through the `payment.confirmed` or `payment.failed` events.

## Rules

- A paid order cannot be cancelled from this API: it requires a refund from payments.
- `Idempotency-Key` is mandatory on `POST /orders` to avoid duplicate orders.
