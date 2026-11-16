# Product vision: Demo Grocery

Demo Grocery is a fictional online grocery store. Our product goal for next year is that **buying is simple, reliable and transparent**.

## Principles

1. **Reliable checkout:** a failed charge must not make the customer lose the order. It must be possible to retry without loading everything again.
2. **Always-correct prices:** the customer sees the same price in the catalog and in the order.
3. **Clear communication:** the customer knows at every moment what happened with the order.

## Epics

- **EPIC-01 Reliable checkout:** card payment and retry of failed charges.
- **EPIC-02 Catalog experience:** real-time prices.
- **EPIC-03 Customer communication:** order status emails.

## Current priority

The priority of the quarter is **FEAT-102 (retry of failed payments)**, because failed charges are the biggest cause of abandonment. It depends on `payments-service` supporting retries natively and on `notifications-service` telling the customer with a retry link.

Product owner: Sofía Mendoza.
