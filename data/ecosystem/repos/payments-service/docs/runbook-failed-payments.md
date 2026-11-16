# Runbook: failed or slow charges

**Symptom:** the rate of `payment.failed` goes up, or charges take more than 30 seconds to resolve.

## Diagnosis

1. Check whether the increase has one reason (for example `provider_timeout`) or several.
2. If it is `provider_timeout`, the external provider is slow or down. Check its status page.
3. If they are card rejections (`card_declined`), it is not an incident: it is normal customer behavior.

## Fix

- Provider down: trigger the on-call alert and tell notifications so the customer gets a clear message.
- Lost events: re-emit them with the `replay-payment-event` tool.
- Charges left in `PENDING` for more than 5 minutes: query the provider manually and update the state.

**Escalation:** payments-team, with 24x7 on call for charge incidents.
