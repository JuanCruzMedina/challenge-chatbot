# Runbook: order stuck in PAYMENT_PENDING

**Symptom:** an order has been in `PAYMENT_PENDING` for more than 15 minutes and the customer received neither a confirmation nor an error.

## Diagnosis

1. Query `GET /orders/{id}` and note the `payment_id`.
2. Query the state of the charge in `payments-service`.
3. If the charge is `CONFIRMED` but the order is still pending, the `payment.confirmed` event was lost.
4. If the charge is `FAILED`, `payment.failed` was lost.

## Fix

- Re-emit the event from `payments-service` (tool `replay-payment-event`).
- Check that `orders-service` moves to `PAID` or `CANCELLED`.
- If the charge does not exist, the order never reached payments: cancel it with `POST /orders/{id}/cancel`.

**Escalation:** orders-team, and payments-team if the problem is in the charge. On call Monday to Friday, 9 to 18.
