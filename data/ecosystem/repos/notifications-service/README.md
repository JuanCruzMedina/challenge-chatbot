# notifications-service

Communications service of Demo Grocery. It exposes no API: it reacts to events and sends messages to the customer.

- **Owner:** communications-team (tech lead: Iván Prado).
- **Events it consumes:** `order.created` (order confirmation), `order.cancelled` (cancellation notice), `payment.failed` (failed-charge notice with a retry link).
- **Channels:** email and push messages.
- **It does not call** any other service directly: everything arrives through events.

If emails arrive late, see `docs/runbook-delayed-emails.md`.
