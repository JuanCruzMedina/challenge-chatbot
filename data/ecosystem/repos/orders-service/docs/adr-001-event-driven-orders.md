# ADR-001: Event-driven orders

**Status:** accepted · **Team:** orders-team

## Context

The purchase flow involves catalog, payments and notifications. A charge can take seconds or fail, and we do not want to block the customer or couple the services.

## Decision

The order is created synchronously, but the result of the charge is communicated **asynchronously** through events (`payment.confirmed`, `payment.failed`). `orders-service` publishes `order.created` and `order.cancelled` so that other services (for example notifications) can react without being called directly.

## Consequences

- Less coupling: notifications does not know about orders, it only listens to events.
- Orders can stay in `PAYMENT_PENDING` if an event is lost. That is why the stuck-order runbook exists.
- Events must be treated as idempotent.
