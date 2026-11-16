# Runbook: delayed emails

**Symptom:** the customer receives the order confirmation more than 10 minutes late, or not at all.

## Diagnosis

1. Check that the event (`order.created`, `payment.failed` or `order.cancelled`) reached the `notifications-service` queue.
2. Check the queue size. If it grows, the (fictional) email provider is throttling sends.
3. If the event did not arrive, the problem is in the service that publishes it, not here.

## Fix

- Queue growing: reduce the send rate and retry later. Messages are not lost.
- Event missing: notify the team that owns the event (orders or payments).

**Escalation:** communications-team, on call Monday to Friday, 9 to 18.
