# payments-api v1

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/payments` | Requests a charge for an order. Returns `payment_id` and state `PENDING`. |
| GET | `/payments/{id}` | Returns the state of the charge: `PENDING`, `CONFIRMED` or `FAILED`. |
| POST | `/payments/{id}/refund` | Refunds a confirmed charge, fully or partially. |

## Asynchronous result

The charge is not resolved in the response. When it finishes, `payment.confirmed` or `payment.failed` is published, with the matching `order_id`.

## Rules

- Amounts in cents with an ISO currency.
- `Idempotency-Key` is mandatory on `POST /payments`.
- v1 does **not** support automatic retries: after a failure, the consumer must create a new charge.
- External provider timeout: 20 seconds. After that the charge is marked `FAILED`.
